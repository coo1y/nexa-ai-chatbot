from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.db.models import UploadedFile
from app.schemas.chat import AttachmentRef, ChatMessage
from app.services.context import ContextBuilder, select_excerpts


def settings(**kw) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


def msg(role: str, content: str, files: list[str] | None = None, idx: int = 0) -> ChatMessage:
    return ChatMessage(
        id=f"m{idx}",
        role=role,
        content=content,
        attachments=[AttachmentRef(file_id=f) for f in files or []],  # type: ignore[arg-type]
    )


def doc(file_id: str, text: str, name: str = "doc.txt") -> UploadedFile:
    now = datetime.now(UTC)
    return UploadedFile(
        id=file_id,
        client_id="c",
        filename=name,
        content_type="text/plain",
        kind="document",
        size_bytes=len(text),
        extracted_text=text,
        char_count=len(text),
        truncated=False,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def image(file_id: str) -> UploadedFile:
    now = datetime.now(UTC)
    return UploadedFile(
        id=file_id,
        client_id="c",
        filename="cat.png",
        content_type="image/png",
        kind="image",
        size_bytes=3,
        data=b"img",
        char_count=0,
        truncated=False,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


FILE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FILE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_system_prompt_has_date_and_rules() -> None:
    built = ContextBuilder(settings()).build(
        messages=[msg("user", "hi")], files={}, capability="fast", now=datetime(2026, 10, 3, tzinfo=UTC)
    )
    system = built.messages[0]["content"]
    assert "Saturday, 03 October 2026" in system
    assert "untrusted data" in system
    assert built.messages[-1] == {"role": "user", "content": "hi"}


def test_documents_are_wrapped_and_independent() -> None:
    files = {FILE_A: doc(FILE_A, "Alpha content", "a.txt"), FILE_B: doc(FILE_B, "Beta content", "b.txt")}
    built = ContextBuilder(settings()).build(
        messages=[msg("user", "Summarize", [FILE_A, FILE_B])], files=files, capability="fast"
    )
    content = built.messages[-1]["content"]
    assert '<document name="a.txt"' in content and '<document name="b.txt"' in content
    assert content.endswith("Summarize")


def test_images_only_sent_to_vision_models() -> None:
    files = {FILE_A: image(FILE_A)}
    messages = [msg("user", "what is this", [FILE_A])]
    vision = ContextBuilder(settings()).build(messages=messages, files=files, capability="vision")
    parts = vision.messages[-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert vision.images_included == 1

    fast = ContextBuilder(settings()).build(messages=messages, files=files, capability="fast")
    assert "not visible to the current model" in fast.messages[-1]["content"]


def test_missing_attachment_placeholder() -> None:
    built = ContextBuilder(settings()).build(messages=[msg("user", "and this?", [FILE_A])], files={}, capability="fast")
    assert "expired or is unavailable" in built.messages[-1]["content"]


def test_long_conversation_drops_oldest_turns() -> None:
    builder = ContextBuilder(settings(context_max_tokens=3000, max_output_tokens=500))
    history = []
    for i in range(40):
        history.append(msg("user", f"question {i} " + "x" * 400, idx=2 * i))
        history.append(msg("assistant", f"answer {i} " + "y" * 400, idx=2 * i + 1))
    history.append(msg("user", "final question", idx=999))
    built = builder.build(messages=history, files={}, capability="fast")
    assert built.omitted_messages > 0
    assert "oldest message(s)" in built.messages[0]["content"]
    assert built.messages[-1]["content"] == "final question"
    assert len(built.messages) < len(history)
    # Most recent turns are kept, in order.
    assert built.messages[-2]["content"].startswith("answer 39")


def test_search_results_attached_to_latest_turn() -> None:
    built = ContextBuilder(settings()).build(
        messages=[msg("user", "news?")],
        files={},
        capability="fast",
        search_results="<search_results>R</search_results>",
    )
    assert built.messages[-1]["content"].startswith("<search_results>")


def test_select_excerpts_prefers_relevant_chunks() -> None:
    filler = "\n\n".join(f"Paragraph {i} about general topics and other things. " * 10 for i in range(60))
    text = filler + "\n\nThe secret launch code word is PINEAPPLE and it was chosen in March.\n\n" + filler
    excerpt, partial = select_excerpts(text, "What is the secret launch code word?", 5000)
    assert partial
    assert "PINEAPPLE" in excerpt
    assert len(excerpt) <= 5000
    assert "[...]" in excerpt


def test_select_excerpts_for_summary_spreads_coverage() -> None:
    text = "\n\n".join(f"Section {i}. " + "content " * 150 for i in range(50))
    excerpt, partial = select_excerpts(text, "Summarize this document", 8000)
    assert partial and "Section 0." in excerpt
    assert any(f"Section {i}." in excerpt for i in range(30, 50))


def test_select_excerpts_short_text_untouched() -> None:
    assert select_excerpts("short", "q", 100) == ("short", False)
