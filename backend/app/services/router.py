"""Low-latency model routing.

Routing is a pure, deterministic function of the request (no extra model call), so it adds
microseconds rather than a network round-trip — the product optimises for first-token latency.
Users can override the capability manually; images always require the vision capability.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.core.config import Settings
from app.schemas.common import Capability, CapabilityChoice

_REASONING_PATTERNS = [
    r"\bstep[- ]by[- ]step\b",
    r"\bprove\b",
    r"\bproof\b",
    r"\bderive\b",
    r"\bexplain why\b",
    r"\bwhy does\b",
    r"\banaly[sz]e\b",
    r"\bcompare\b",
    r"\btrade-?offs?\b",
    r"\bpros and cons\b",
    r"\boptimi[sz]e\b",
    r"\balgorithm\b",
    r"\btime complexity\b",
    r"\bbig-?o\b",
    r"\barchitecture\b",
    r"\bdesign (a|an|the)\b",
    r"\brefactor\b",
    r"\bdebug\b",
    r"\broot cause\b",
    r"\bplan\b",
    r"\bstrategy\b",
    r"\bevaluate\b",
    r"\bequation\b",
    r"\bintegral\b",
    r"\bprobability\b",
    r"\btheorem\b",
    r"\blogic puzzle\b",
    r"\briddle\b",
    r"\bthink (carefully|hard)\b",
    r"\bin depth\b",
    r"\bdetailed\b",
]
_REASONING_RX = [re.compile(p, re.I) for p in _REASONING_PATTERNS]
_CODE_RX = re.compile(
    r"```|\bdef \w+\(|\bfunction \w*\(|\bclass \w+|Traceback \(most recent call last\)|\bexception\b|=>|#include", re.I
)
_CODING_WORDS_RX = re.compile(
    r"\b(python|javascript|typescript|java|c\+\+|c#|golang|rust|kotlin|swift|php|ruby|sql|regex|bash|html|css|react|"
    r"function|script|code|snippet|compile|syntax|api|bug|unit test)\b",
    re.I,
)
_IMAGE_REFERENCE_RX = re.compile(r"\b(image|picture|photo|screenshot|diagram|chart|figure|it|this|that)\b", re.I)

_SEARCH_PATTERNS: list[tuple[str, str]] = [
    (r"\b(search|google|look up|browse)\b.{0,20}\b(web|internet|online|for)\b", "user asked to search"),
    (r"^\s*(search|google|look up)\b", "user asked to search"),
    (
        r"\b(latest|newest|recent|recently|current|currently|today|tonight|yesterday|this (week|month|year)|right now|breaking)\b",
        "time-sensitive request",
    ),
    (r"\bnews\b|\bheadlines?\b", "news request"),
    (r"\b(price|stock|exchange rate|weather|forecast|score|standings|election|release date)\b", "live data request"),
    (r"\bwho (won|is winning|is the (current|new))\b", "current events"),
]
_SEARCH_RX = [(re.compile(p, re.I), reason) for p, reason in _SEARCH_PATTERNS]
_SEARCH_PREFIX_RX = re.compile(
    r"^\s*(please\s+)?(can you\s+|could you\s+)?(search( the)?( web| internet| online)?( for)?|google|look up|find( me)?)\s*[:,-]?\s*",
    re.I,
)
# Requests that are about the conversation itself never need the web.
_NO_SEARCH_RX = re.compile(r"\b(this|the|my|attached|uploaded) (document|file|pdf|image|photo|code|text)\b", re.I)


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: Literal["auto", "manual"]
    capability: Capability
    model: str
    reason: str
    search: bool
    search_reason: str | None
    search_query: str | None


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(
        self,
        *,
        requested: CapabilityChoice,
        text: str,
        latest_has_images: bool,
        history_has_images: bool,
        has_documents: bool,
        web_search_requested: bool,
    ) -> RouteDecision:
        capability, reason = self._capability(requested, text, latest_has_images, history_has_images)
        search_reason = self.search_reason(text, web_search_requested, has_documents or latest_has_images)
        return RouteDecision(
            mode="auto" if requested == "auto" else "manual",
            capability=capability,
            model=self.settings.model_for(capability),
            reason=reason,
            search=search_reason is not None,
            search_reason=search_reason,
            search_query=build_search_query(text) if search_reason else None,
        )

    def _capability(
        self, requested: CapabilityChoice, text: str, latest_has_images: bool, history_has_images: bool
    ) -> tuple[Capability, str]:
        if latest_has_images:
            if requested in ("auto", "vision"):
                return "vision", "image attached"
            return "vision", f"image attached (overrides {requested}: only vision models can see images)"
        if requested != "auto":
            return requested, "selected by user"
        if history_has_images and _IMAGE_REFERENCE_RX.search(text) and len(text) < 400:
            return "vision", "follow-up about an earlier image"
        score, signals = reasoning_score(text)
        if score >= 2:
            return "reasoning", "complex request: " + ", ".join(signals[:3])
        if _CODE_RX.search(text) or _CODING_WORDS_RX.search(text):
            return "fast", "coding request"
        return "fast", "general request"

    @staticmethod
    def search_reason(text: str, requested: bool, about_attachment: bool) -> str | None:
        if requested:
            return "requested by user"
        if about_attachment or _NO_SEARCH_RX.search(text):
            return None
        for rx, reason in _SEARCH_RX:
            if rx.search(text):
                return reason
        year = datetime.now(UTC).year
        if re.search(rf"\b({year}|{year + 1})\b", text):
            return "mentions the current year"
        return None


def reasoning_score(text: str) -> tuple[int, list[str]]:
    signals = [m.group(0).lower() for rx in _REASONING_RX if (m := rx.search(text))]
    score = len(signals)
    if len(text) > 1500:
        score += 1
        signals.append("long input")
    code_lines = text.count("\n") if "```" in text else 0
    if code_lines > 40:
        score += 1
        signals.append("large code block")
    if "Traceback (most recent call last)" in text:
        score += 1
        signals.append("stack trace")
    return score, signals


def build_search_query(text: str) -> str:
    query = _SEARCH_PREFIX_RX.sub("", text.strip())
    query = re.sub(r"\s+", " ", query).strip(" ?.!")
    if len(query) > 300:
        first_sentence = re.split(r"(?<=[.?!])\s", query, maxsplit=1)[0]
        query = first_sentence[:300]
    return query or text.strip()[:300]
