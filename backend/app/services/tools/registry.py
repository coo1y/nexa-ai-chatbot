"""Tool registry: one place to list, describe and safely execute assistant tools."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.services.tools.base import Tool, ToolContext, ToolInputError, ToolResult
from app.services.tools.calculator import calculator_tool
from app.services.tools.data_process import data_process_tool
from app.services.tools.datetime_tool import datetime_tool
from app.services.tools.units import unit_convert_tool
from app.services.tools.web_search import SearchError, SearchProvider, make_web_search_tool

logger = logging.getLogger(__name__)

MAX_ARGUMENT_CHARS = 250_000


@dataclass(slots=True)
class ToolExecution:
    status: Literal["success", "error"]
    result: ToolResult
    duration_ms: int


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        tools = self._tools.values() if names is None else [self._tools[n] for n in names if n in self._tools]
        return [tool.spec() for tool in tools]

    @staticmethod
    def parse_arguments(raw: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if len(raw) > MAX_ARGUMENT_CHARS:
            raise ToolInputError("tool arguments too large")
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise ToolInputError("tool arguments are not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ToolInputError("tool arguments must be a JSON object")
        return parsed

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolExecution:
        """Run a tool with a timeout. Failures become error results the model can recover from."""
        started = time.perf_counter()
        tool = self._tools.get(name)
        status: Literal["success", "error"]
        try:
            if tool is None:
                raise ToolInputError(f"unknown tool '{name}'")
            result = await asyncio.wait_for(tool.handler(args, ctx), timeout=tool.timeout_seconds)
            status = "success"
        except ToolInputError as exc:
            result = ToolResult(content=f"Tool error: {exc}", summary=f"Could not run: {exc}")
            status = "error"
        except (SearchError, TimeoutError) as exc:
            logger.warning("tool %s failed: %s", name, exc)
            result = ToolResult(
                content="Tool error: the service is temporarily unavailable. Answer without it and say so.",
                summary="Service temporarily unavailable",
            )
            status = "error"
        except Exception:
            logger.exception("tool %s crashed", name)
            result = ToolResult(content="Tool error: unexpected failure.", summary="Unexpected tool failure")
            status = "error"
        return ToolExecution(status=status, result=result, duration_ms=int((time.perf_counter() - started) * 1000))


def build_registry(search_provider: SearchProvider, max_results: int) -> ToolRegistry:
    return ToolRegistry(
        [
            calculator_tool,
            unit_convert_tool,
            datetime_tool,
            data_process_tool,
            make_web_search_tool(search_provider, max_results),
        ]
    )
