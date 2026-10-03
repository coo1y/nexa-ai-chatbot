"""Upload → analyse workflows: documents, images, multiple files, ownership, expiry."""

from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import update

from app.db.base import utcnow
from app.db.models import UploadedFile
from app.services.llm.mock import MockProvider
from tests.conftest import chat, text_of, user_message
from tests.fixtures import make_docx, make_image, make_pdf


async def upload(client: httpx.AsyncClient, name: str, data: bytes, **kwargs: Any) -> httpx.Response:
    return await client.post("/files", files={"file": (name, data)}, **kwargs)


async def test_upload_and_summarise_document(client: httpx.AsyncClient, mock_llm: MockProvider, contract: Any) -> None:
    response = await upload(client, "report.pdf", make_pdf(["Revenue grew 20% in Q3.", "Outlook is positive."]))
    assert response.status_code == 201
    meta = response.json()
    contract("FileMeta", meta)
    assert meta["kind"] == "document" and meta["page_count"] == 2

    events = await chat(client, [user_message("Summarize this document", [meta["id"]])])
    assert "**Summary:**" in text_of(events)
    prompt = mock_llm.calls[-1].messages[-1]["content"]
    assert '<document name="report.pdf"' in prompt and "Revenue grew 20% in Q3." in prompt


async def test_document_question_answering_across_turns(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    meta = (await upload(client, "policy.txt", b"Employees get 25 days of annual leave.")).json()
    first = user_message("Read this", [meta["id"]], msg_id="u1")
    events = await chat(
        client,
        [
            first,
            {"id": "a1", "role": "assistant", "content": "Done."},
            user_message("How many leave days?", msg_id="u2"),
        ],
    )
    assert "Based on the document" in text_of(events)
    # The document from an earlier turn is still in context for follow-ups.
    assert "25 days of annual leave" in str(mock_llm.calls[-1].messages)


async def test_multiple_files_analysed_independently(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    a = (await upload(client, "a.docx", make_docx(["Alpha project plan"]))).json()
    b = (await upload(client, "b.md", b"# Beta notes")).json()
    await chat(client, [user_message("Summarize each file", [a["id"], b["id"]])])
    prompt = mock_llm.calls[-1].messages[-1]["content"]
    assert prompt.count("<document ") == 2
    assert "Analyse each uploaded file independently" in mock_llm.calls[-1].messages[0]["content"]


async def test_image_upload_routes_to_vision(client: httpx.AsyncClient, mock_llm: MockProvider, contract: Any) -> None:
    response = await upload(client, "photo.jpg", make_image(3000, 2000, fmt="JPEG"))
    meta = response.json()
    contract("FileMeta", meta)
    assert meta["kind"] == "image" and max(meta["width"], meta["height"]) == 1568

    events = await chat(client, [user_message("What is in this picture?", [meta["id"]])])
    assert events[0][1]["routing"]["capability"] == "vision"
    assert "Mock vision analysis" in text_of(events)
    parts = mock_llm.calls[-1].messages[-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


async def test_files_are_private_to_their_client(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    meta = (await upload(client, "secret.txt", b"top secret plans")).json()
    other = {"X-Client-Id": "another-client-99"}
    assert (await client.get(f"/files/{meta['id']}", headers=other)).status_code == 404
    assert (await client.delete(f"/files/{meta['id']}", headers=other)).status_code == 404
    response = await client.post(
        "/chat/stream",
        json={"conversation_id": "c", "messages": [user_message("read it", [meta["id"]])]},
        headers=other,
    )
    assert response.status_code == 200
    assert "top secret plans" not in str(mock_llm.calls[-1].messages)


async def test_get_and_delete_file(client: httpx.AsyncClient, contract: Any) -> None:
    meta = (await upload(client, "notes.txt", b"hello")).json()
    fetched = await client.get(f"/files/{meta['id']}")
    assert fetched.status_code == 200 and fetched.json() == meta
    assert (await client.delete(f"/files/{meta['id']}")).status_code == 204
    missing = await client.get(f"/files/{meta['id']}")
    assert missing.status_code == 404
    contract("ErrorResponse", missing.json())


async def test_expired_files_are_unavailable(client: httpx.AsyncClient, container: Any, mock_llm: MockProvider) -> None:
    meta = (await upload(client, "old.txt", b"ancient text")).json()
    async with container.db.session_factory() as session:
        await session.execute(
            update(UploadedFile).where(UploadedFile.id == meta["id"]).values(expires_at=utcnow() - timedelta(minutes=1))
        )
        await session.commit()
    assert (await client.get(f"/files/{meta['id']}")).status_code == 404
    await chat(client, [user_message("what did it say?", [meta["id"]])])
    assert "expired or is unavailable" in str(mock_llm.calls[-1].messages)


async def test_upload_rejections(client: httpx.AsyncClient, container: Any, contract: Any) -> None:
    unsupported = await upload(client, "malware.exe", b"MZ\x90\x00")
    assert unsupported.status_code == 415
    contract("ErrorResponse", unsupported.json())
    assert "Unsupported file type" in unsupported.json()["error"]["message"]

    container.settings.upload_max_bytes = 1024
    too_big = await upload(client, "big.txt", b"a" * 2048)
    assert too_big.status_code == 413

    empty = await upload(client, "empty.txt", b"")
    assert empty.status_code == 422
