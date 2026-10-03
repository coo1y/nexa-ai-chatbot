import io

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.errors import PayloadTooLarge, UnsupportedFile, ValidationFailed
from app.services.files import FileService
from tests.fixtures import make_docx, make_image, make_pdf, make_xlsx


@pytest.fixture
def service() -> FileService:
    return FileService(Settings(_env_file=None, upload_max_bytes=2 * 1024 * 1024, image_max_dimension=100))  # type: ignore[call-arg]


async def test_plain_text_and_markdown(service: FileService) -> None:
    result = await service.process("notes.md", "# Title\n\nHello wörld".encode())
    assert result.kind == "document"
    assert result.content_type == "text/markdown"
    assert "Hello wörld" in (result.text or "")


async def test_cp1252_fallback(service: FileService) -> None:
    result = await service.process("legacy.txt", "café".encode("cp1252"))
    assert result.text == "café"


async def test_pdf_extraction_with_pages(service: FileService) -> None:
    result = await service.process("report.pdf", make_pdf(["Quarterly revenue grew", "Costs fell"]))
    assert result.page_count == 2
    assert "--- Page 1 ---" in (result.text or "")
    assert "Costs fell" in (result.text or "")


async def test_docx_extraction_includes_tables(service: FileService) -> None:
    result = await service.process("memo.docx", make_docx(["First paragraph", "Second paragraph"]))
    assert "Second paragraph" in (result.text or "")
    assert "cell A | cell B" in (result.text or "")


async def test_xlsx_extraction(service: FileService) -> None:
    result = await service.process("sales.xlsx", make_xlsx([["region", "sales"], ["north", 100]]))
    assert "--- Sheet: Sales ---" in (result.text or "")
    assert "north,100" in (result.text or "")


async def test_html_strips_scripts(service: FileService) -> None:
    html = b"<html><script>alert(1)</script><body><h1>Title</h1><p>Body text</p></body></html>"
    result = await service.process("page.html", html)
    assert "alert" not in (result.text or "")
    assert "Title\nBody text" in (result.text or "")


async def test_image_is_downscaled_and_metadata_stripped(service: FileService) -> None:
    result = await service.process("photo.jpg", make_image(400, 200, fmt="JPEG", exif=True))
    assert result.kind == "image"
    assert (result.width, result.height) == (100, 50)
    assert result.content_type == "image/jpeg"
    reopened = Image.open(io.BytesIO(result.image_bytes or b""))
    assert "SecretCameraMaker" not in str(dict(reopened.getexif()))


async def test_transparent_png_stays_png(service: FileService) -> None:
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    result = await service.process("logo.png", out.getvalue())
    assert result.content_type == "image/png"


@pytest.mark.parametrize(
    ("name", "data", "error"),
    [
        ("virus.exe", b"MZ....", UnsupportedFile),
        ("fake.png", b"not an image", UnsupportedFile),
        ("fake.pdf", b"hello", UnsupportedFile),
        ("fake.docx", b"PK not a zip", UnsupportedFile),
        ("blob.txt", b"\x00\x01\x02" * 100, UnsupportedFile),
        ("empty.txt", b"", ValidationFailed),
        ("blank.txt", b"   \n  ", ValidationFailed),
    ],
)
async def test_rejects_invalid_files(service: FileService, name: str, data: bytes, error: type[Exception]) -> None:
    with pytest.raises(error):
        await service.process(name, data)


async def test_size_limit(service: FileService) -> None:
    with pytest.raises(PayloadTooLarge):
        await service.process("big.txt", b"a" * (2 * 1024 * 1024 + 1))


def test_sanitize_filename() -> None:
    assert FileService.sanitize_filename("../../etc/passwd") == "passwd"
    assert FileService.sanitize_filename("C:\\Users\\me\\report<1>.pdf") == "report1.pdf"
    assert FileService.sanitize_filename(None) == "upload"
