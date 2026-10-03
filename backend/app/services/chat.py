"""Chat orchestration pipeline.

    validate -> load attachments -> route -> safety -> (search) -> assemble context
             -> model + tool loop (with retries) -> stream events -> log telemetry

The service yields ``(event_name, payload)`` pairs; the API layer turns them into SSE.
"""

import asyncio
import logging
import random
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

import anyio
from pydantic import BaseModel

from app.core.config import Settings
from app.db.models import ChatRequestLog, UploadedFile
from app.db.repositories import FileRepository, RequestLogRepository
from app.db.session import Database
from app.schemas.chat import (
    ChatRequest,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    RoutingInfo,
    SafetyEvent,
    SourcesEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    Usage,
)
from app.services.context import ContextBuilder
from app.services.llm.base import CompletionRequest, Finish, LLMError, LLMEvent, LLMProvider, TextDelta, ToolCallsReady
from app.services.router import ModelRouter
from app.services.safety import SafetyContext, SafetyService
from app.services.tools.base import ToolContext, ToolInputError, ToolResult
from app.services.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

StreamItem = tuple[str, BaseModel]

FRIENDLY_ERRORS = {
    "upstream_bad_request": "The AI model couldn't process this request. Try shortening it or removing an attachment.",
    "internal_error": "Something went wrong while generating a response. Please try again.",
}
DEFAULT_FRIENDLY_ERROR = "The AI service is temporarily unavailable. Please try again in a moment."


@dataclass(slots=True)
class _RunState:
    request_id: str
    started: float
    ttft_ms: int | None = None
    retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tools_used: list[str] = field(default_factory=list)
    status: str = "error"
    error_code: str | None = None

    def mark_first_output(self) -> None:
        if self.ttft_ms is None:
            self.ttft_ms = int((time.perf_counter() - self.started) * 1000)

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        db: Database,
        llm: LLMProvider,
        tools: ToolRegistry,
        safety: SafetyService,
        router: ModelRouter,
        context_builder: ContextBuilder,
    ) -> None:
        self.settings = settings
        self.db = db
        self.llm = llm
        self.tools = tools
        self.safety = safety
        self.router = router
        self.context_builder = context_builder

    async def stream(self, request: ChatRequest, client_id: str) -> AsyncGenerator[StreamItem]:
        state = _RunState(request_id=str(uuid.uuid4()), started=time.perf_counter())
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        latest = request.messages[-1]
        log = ChatRequestLog(
            id=state.request_id,
            client_id=client_id,
            conversation_id=request.conversation_id,
            routing_mode="auto" if request.capability == "auto" else "manual",
            capability=request.capability if request.capability != "auto" else "fast",
            model="",
            message_count=len(request.messages),
        )
        try:
            files = await self._load_files(request, client_id)
            latest_files = [files[a.file_id] for a in latest.attachments if a.file_id in files]
            earlier_files = [
                files[a.file_id] for m in request.messages[:-1] for a in m.attachments if a.file_id in files
            ]
            latest_has_images = any(f.kind == "image" for f in latest_files)
            decision = self.router.route(
                requested=request.capability,
                text=latest.content,
                latest_has_images=latest_has_images,
                history_has_images=any(f.kind == "image" for f in earlier_files),
                has_documents=any(f.kind == "document" for f in latest_files),
                web_search_requested=request.web_search,
            )
            log.capability, log.model, log.route_reason = decision.capability, decision.model, decision.reason[:255]
            yield (
                "start",
                StartEvent(
                    request_id=state.request_id,
                    message_id=message_id,
                    routing=RoutingInfo(
                        mode=decision.mode, capability=decision.capability, model=decision.model, reason=decision.reason
                    ),
                ),
            )

            verdict = await self.safety.check_request(
                SafetyContext(
                    text=latest.content,
                    capability=decision.capability,
                    has_images=latest_has_images,
                    web_search=decision.search,
                )
            )
            log.safety_action = verdict.action.value
            if verdict.blocked:
                yield "safety", SafetyEvent(action="block", category=verdict.category, message=verdict.user_message)
                state.mark_first_output()
                yield "delta", DeltaEvent(text=verdict.user_message)
                state.status = "blocked"
                yield "done", self._done(state, "blocked")
                return
            if verdict.user_message:
                yield (
                    "safety",
                    SafetyEvent(action="allow_with_guidance", category=verdict.category, message=verdict.user_message),
                )

            tool_ctx = ToolContext()
            search_results: str | None = None
            if decision.search and decision.search_query:
                async for item in self._run_tool(
                    "search_prefetch", "web_search", {"query": decision.search_query}, tool_ctx, state
                ):
                    if isinstance(item, ToolResult):
                        search_results = item.content if item.sources else None
                    else:
                        yield item

            built = self.context_builder.build(
                messages=request.messages,
                files=files,
                capability=decision.capability,
                search_results=search_results,
                guidance=verdict.guidance,
            )
            llm_messages = built.messages
            finish_reason = "stop"
            for iteration in range(self.settings.max_tool_iterations + 1):
                offer_tools = iteration < self.settings.max_tool_iterations
                completion = CompletionRequest(
                    model=decision.model,
                    messages=llm_messages,
                    tools=self.tools.specs() if offer_tools else None,
                    max_tokens=self.settings.max_output_tokens,
                    temperature=self.settings.llm_temperature,
                )
                pending_calls = None
                text_parts: list[str] = []
                async for event in self._stream_with_retry(completion, state):
                    if isinstance(event, TextDelta):
                        state.mark_first_output()
                        text_parts.append(event.text)
                        yield "delta", DeltaEvent(text=event.text)
                    elif isinstance(event, ToolCallsReady):
                        pending_calls = event.calls
                    elif isinstance(event, Finish):
                        finish_reason = event.reason
                        state.prompt_tokens += event.prompt_tokens or 0
                        state.completion_tokens += event.completion_tokens or 0
                if not pending_calls:
                    break
                llm_messages.append(
                    {
                        "role": "assistant",
                        "content": "".join(text_parts) or None,
                        "tool_calls": [
                            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                            for c in pending_calls
                        ],
                    }
                )
                for call in pending_calls:
                    tool_output = "Tool error: no result."
                    invalid: str | None = None
                    try:
                        args = self.tools.parse_arguments(call.arguments)
                    except ToolInputError as exc:
                        args, invalid = {}, str(exc)
                    async for item in self._run_tool(call.id, call.name, args, tool_ctx, state, invalid=invalid):
                        if isinstance(item, ToolResult):
                            tool_output = item.content
                        else:
                            yield item
                    llm_messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_output})

            state.status = "completed"
            yield "done", self._done(state, "length" if finish_reason == "length" else "stop")
        except LLMError as exc:
            logger.warning("chat request failed after %s retries: %s (%s)", state.retries, exc, exc.code)
            state.status, state.error_code = "error", exc.code
            yield (
                "error",
                ErrorEvent(
                    code=exc.code, message=FRIENDLY_ERRORS.get(exc.code, DEFAULT_FRIENDLY_ERROR), retryable=True
                ),
            )
            yield "done", self._done(state, "error")
        except (asyncio.CancelledError, GeneratorExit):
            state.status = "stopped"
            raise
        except Exception:
            logger.exception("unexpected chat failure")
            state.status, state.error_code = "error", "internal_error"
            yield "error", ErrorEvent(code="internal_error", message=FRIENDLY_ERRORS["internal_error"], retryable=True)
            yield "done", self._done(state, "error")
        finally:
            await self._save_log(log, state)

    async def _run_tool(
        self,
        call_id: str,
        name: str,
        args: dict[str, Any],
        ctx: ToolContext,
        state: _RunState,
        *,
        invalid: str | None = None,
    ) -> AsyncIterator[StreamItem | ToolResult]:
        """Safety-check, announce, execute and report a tool call. Yields the ToolResult last."""
        tool = self.tools.get(name)
        yield (
            "tool_call",
            ToolCallEvent(id=call_id, name=name, label=tool.label if tool else name, input=_display_args(args)),
        )
        state.mark_first_output()
        verdict = self.safety.check_tool_call(name, args)
        sources_before = len(ctx.sources)
        status: Literal["success", "error", "blocked"]
        if invalid is not None:
            result = ToolResult(content=f"Tool error: {invalid}", summary=f"Could not run: {invalid}")
            status, duration_ms = "error", 0
        elif verdict.blocked:
            result = ToolResult(
                content=f"Tool call blocked by safety policy ({verdict.user_message or verdict.category}). "
                "Do not retry it; explain briefly to the user.",
                summary="Blocked by safety policy",
            )
            status, duration_ms = "blocked", 0
        else:
            execution = await self.tools.execute(name, args, ctx)
            result, status, duration_ms = execution.result, execution.status, execution.duration_ms
            state.tools_used.append(name)
        yield (
            "tool_result",
            ToolResultEvent(
                id=call_id, name=name, status=status, summary=result.summary[:300], duration_ms=duration_ms
            ),
        )
        if len(ctx.sources) > sources_before:
            yield "sources", SourcesEvent(sources=list(ctx.sources))
        yield result

    async def _stream_with_retry(self, request: CompletionRequest, state: _RunState) -> AsyncIterator[LLMEvent]:
        """Attempt, then retry up to ``llm_max_retries`` times with exponential backoff.

        Retries are only transparent while nothing has been streamed for this attempt;
        once output has reached the user, a failure surfaces as an error instead.
        """
        attempts = self.settings.llm_max_retries + 1
        for attempt in range(attempts):
            emitted = False
            try:
                async for event in self.llm.stream(request):
                    if isinstance(event, (TextDelta, ToolCallsReady)):
                        emitted = True
                    yield event
                return
            except LLMError as exc:
                if not exc.retryable or emitted or attempt == attempts - 1:
                    raise
                state.retries += 1
                delay = self.settings.llm_retry_base_delay_seconds * (2**attempt)
                delay *= 0.75 + random.random() / 2  # noqa: S311 # nosec B311 - retry jitter, not cryptography
                logger.info("retrying model call (%s/%s) in %.2fs: %s", attempt + 1, attempts - 1, delay, exc.code)
                await asyncio.sleep(delay)

    async def _load_files(self, request: ChatRequest, client_id: str) -> dict[str, UploadedFile]:
        ids = list({a.file_id for m in request.messages for a in m.attachments})
        if not ids:
            return {}
        async with self.db.session_factory() as session:
            return await FileRepository(session).get_many_for_client(ids, client_id)

    @staticmethod
    def _done(state: _RunState, finish_reason: str) -> DoneEvent:
        return DoneEvent(
            finish_reason=finish_reason,  # type: ignore[arg-type]
            usage=Usage(
                prompt_tokens=state.prompt_tokens or None,
                completion_tokens=state.completion_tokens or None,
            ),
            ttft_ms=state.ttft_ms,
            duration_ms=state.elapsed_ms,
        )

    async def _save_log(self, log: ChatRequestLog, state: _RunState) -> None:
        log.status = state.status
        log.error_code = state.error_code
        log.retries = state.retries
        log.tools_used = state.tools_used
        log.search_used = "web_search" in state.tools_used
        log.ttft_ms = state.ttft_ms
        log.duration_ms = state.elapsed_ms
        log.prompt_tokens = state.prompt_tokens or None
        log.completion_tokens = state.completion_tokens or None
        if not log.model:
            log.model = "unrouted"
        # Shielded so that a client disconnect (stop generation) still records telemetry.
        with anyio.CancelScope(shield=True):
            try:
                async with self.db.session_factory() as session:
                    await RequestLogRepository(session).add(log)
            except Exception as exc:  # noqa: BLE001 - telemetry is best-effort and must never break a response
                logger.warning("chat telemetry not persisted (%s: %s)", type(exc).__name__, str(exc)[:200])


def _display_args(args: dict[str, Any]) -> dict[str, Any]:
    """Arguments as shown in the tool activity stream (long values abbreviated)."""
    shown: dict[str, Any] = {}
    for key, value in list(args.items())[:10]:
        if isinstance(value, str) and len(value) > 200:
            shown[key] = value[:200] + f"… ({len(value)} chars)"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            shown[key] = value
        else:
            shown[key] = str(value)[:200]
    return shown
