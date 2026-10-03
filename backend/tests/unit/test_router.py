import pytest

from app.core.config import Settings
from app.services.router import ModelRouter, build_search_query


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter(Settings(_env_file=None))  # type: ignore[call-arg]


def route(router: ModelRouter, text: str, **kwargs):  # type: ignore[no-untyped-def]
    params = {
        "requested": "auto",
        "latest_has_images": False,
        "history_has_images": False,
        "has_documents": False,
        "web_search_requested": False,
    }
    params.update(kwargs)
    return router.route(text=text, **params)


def test_simple_question_is_fast(router: ModelRouter) -> None:
    decision = route(router, "What is the capital of France?")
    assert decision.capability == "fast"
    assert decision.mode == "auto"
    assert decision.model == router.settings.model_fast


def test_complex_reasoning(router: ModelRouter) -> None:
    decision = route(router, "Explain why this algorithm is O(n log n), step by step, and compare it with quicksort.")
    assert decision.capability == "reasoning"
    assert "complex request" in decision.reason


def test_simple_coding_is_fast(router: ModelRouter) -> None:
    decision = route(router, "Write a python function to reverse a string: def rev(s):")
    assert decision.capability == "fast"
    assert decision.reason == "coding request"


def test_stack_trace_debugging_is_reasoning(router: ModelRouter) -> None:
    decision = route(router, "Please debug this:\nTraceback (most recent call last):\n  File x\nKeyError: 'a'")
    assert decision.capability == "reasoning"


def test_image_routes_to_vision_even_with_manual_override(router: ModelRouter) -> None:
    assert route(router, "What is this?", latest_has_images=True).capability == "vision"
    decision = route(router, "What is this?", latest_has_images=True, requested="fast")
    assert decision.capability == "vision"
    assert "overrides fast" in decision.reason


def test_follow_up_about_earlier_image(router: ModelRouter) -> None:
    assert route(router, "What colour is it?", history_has_images=True).capability == "vision"


def test_manual_selection(router: ModelRouter) -> None:
    decision = route(router, "hi", requested="reasoning")
    assert (decision.capability, decision.mode, decision.reason) == ("reasoning", "manual", "selected by user")


@pytest.mark.parametrize(
    "text",
    [
        "What's the latest news about AI?",
        "bitcoin price today",
        "Who won the match yesterday?",
        "search the web for rust 2.0",
    ],
)
def test_auto_search_detection(router: ModelRouter, text: str) -> None:
    decision = route(router, text)
    assert decision.search is True
    assert decision.search_query


def test_no_search_for_timeless_or_attachment_questions(router: ModelRouter) -> None:
    assert route(router, "Explain recursion").search is False
    assert route(router, "What is the latest section in this document?").search is False
    assert route(router, "latest summary", has_documents=True).search is False


def test_user_requested_search(router: ModelRouter) -> None:
    decision = route(router, "Explain recursion", web_search_requested=True)
    assert decision.search and decision.search_reason == "requested by user"


def test_build_search_query_strips_prefix() -> None:
    assert build_search_query("Can you search the web for: best laptops 2026?") == "best laptops 2026"
    assert len(build_search_query("word " * 200)) <= 300
