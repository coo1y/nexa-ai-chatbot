"""Composition root: builds every service once per application instance.

Tests construct a ``Container`` with fakes (mock LLM, mock search, temp database) instead
of patching module globals.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.db.session import Database
from app.services.chat import ChatService
from app.services.context import ContextBuilder
from app.services.files import FileService
from app.services.llm.base import LLMProvider
from app.services.llm.factory import build_provider
from app.services.router import ModelRouter
from app.services.safety import SafetyService
from app.services.tools.registry import ToolRegistry, build_registry
from app.services.tools.web_search import SearchProvider, build_search_provider


@dataclass
class Container:
    settings: Settings
    db: Database
    llm: LLMProvider
    search: SearchProvider
    tools: ToolRegistry
    safety: SafetyService
    router: ModelRouter
    files: FileService
    chat: ChatService
    rate_limiter: RateLimiter


def build_container(
    settings: Settings,
    *,
    llm: LLMProvider | None = None,
    search: SearchProvider | None = None,
    db: Database | None = None,
) -> Container:
    db = db or Database(settings)
    llm = llm or build_provider(settings)
    search = search or build_search_provider(settings)
    tools = build_registry(search, settings.search_max_results)
    safety = SafetyService(llm, settings.safety_model)
    router = ModelRouter(settings)
    chat = ChatService(
        settings=settings,
        db=db,
        llm=llm,
        tools=tools,
        safety=safety,
        router=router,
        context_builder=ContextBuilder(settings),
    )
    return Container(
        settings=settings,
        db=db,
        llm=llm,
        search=search,
        tools=tools,
        safety=safety,
        router=router,
        files=FileService(settings),
        chat=chat,
        rate_limiter=RateLimiter(),
    )
