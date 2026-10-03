"""Tool abstractions shared by every assistant tool."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.schemas.chat import Source


class ToolInputError(Exception):
    """The model (or user) supplied arguments the tool cannot work with."""


@dataclass(slots=True)
class ToolResult:
    # Text handed back to the model.
    content: str
    # One-line, user-facing description shown in the tool activity stream.
    summary: str
    sources: list[Source] = field(default_factory=list)


@dataclass(slots=True)
class ToolContext:
    """Per-request state tools may need (e.g. the running citation counter)."""

    next_source_id: int = 1
    sources: list[Source] = field(default_factory=list)

    def register_sources(self, items: list[dict[str, str]]) -> list[Source]:
        from urllib.parse import urlparse

        added: list[Source] = []
        known = {s.url: s for s in self.sources}
        for item in items:
            url = item["url"]
            if url in known:
                added.append(known[url])
                continue
            source = Source(
                id=self.next_source_id,
                title=item.get("title") or url,
                url=url,
                domain=urlparse(url).netloc.removeprefix("www."),
                snippet=(item.get("snippet") or "")[:500],
            )
            self.next_source_id += 1
            self.sources.append(source)
            known[url] = source
            added.append(source)
        return added


Handler = Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]


@dataclass(slots=True)
class Tool:
    name: str
    label: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    timeout_seconds: float = 15.0

    def spec(self) -> dict[str, Any]:
        """OpenAI-compatible function-calling schema."""
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }
