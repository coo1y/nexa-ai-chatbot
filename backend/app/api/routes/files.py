import uuid
from datetime import timedelta

from fastapi import APIRouter, File, Request, Response, UploadFile, status

from app.api.deps import ClientIdDep, ContainerDep, SessionDep, enforce_rate_limit
from app.core.errors import NotFoundError, PayloadTooLarge
from app.db.base import utcnow
from app.db.models import UploadedFile
from app.db.repositories import FileRepository
from app.schemas.common import ErrorResponse
from app.schemas.files import FileMeta

router = APIRouter(prefix="/files", tags=["files"])

_ERRORS = {
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    415: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _to_meta(row: UploadedFile) -> FileMeta:
    return FileMeta(
        id=row.id,
        filename=row.filename,
        kind=row.kind,  # type: ignore[arg-type]
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        char_count=row.char_count,
        page_count=row.page_count,
        truncated=row.truncated,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


@router.post(
    "",
    operation_id="uploadFile",
    summary="Upload a document or image for analysis",
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,  # type: ignore[arg-type]
)
async def upload_file(
    request: Request,
    container: ContainerDep,
    session: SessionDep,
    client_id: ClientIdDep,
    file: UploadFile = File(...),
) -> FileMeta:
    settings = container.settings
    enforce_rate_limit(container, request, client_id, "upload", settings.rate_limit_upload_per_minute)
    data = await file.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise PayloadTooLarge(f"The file is larger than the {settings.upload_max_bytes // (1024 * 1024)} MB limit.")
    filename = container.files.sanitize_filename(file.filename)
    processed = await container.files.process(filename, data)
    now = utcnow()
    row = UploadedFile(
        id=str(uuid.uuid4()),
        client_id=client_id,
        filename=filename,
        content_type=processed.content_type,
        kind=processed.kind,
        size_bytes=len(data),
        extracted_text=processed.text,
        char_count=len(processed.text or ""),
        page_count=processed.page_count,
        truncated=processed.truncated,
        data=processed.image_bytes,
        width=processed.width,
        height=processed.height,
        created_at=now,
        expires_at=now + timedelta(hours=settings.upload_retention_hours),
    )
    await FileRepository(session).add(row)
    return _to_meta(row)


@router.get("/{file_id}", operation_id="getFile", summary="Get uploaded file metadata", responses=_ERRORS)  # type: ignore[arg-type]
async def get_file(file_id: str, session: SessionDep, client_id: ClientIdDep) -> FileMeta:
    row = await FileRepository(session).get_for_client(file_id, client_id)
    if row is None:
        raise NotFoundError("File not found or expired.")
    return _to_meta(row)


@router.delete(
    "/{file_id}",
    operation_id="deleteFile",
    summary="Delete an uploaded file",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,  # type: ignore[arg-type]
)
async def delete_file(file_id: str, session: SessionDep, client_id: ClientIdDep) -> Response:
    if not await FileRepository(session).delete_for_client(file_id, client_id):
        raise NotFoundError("File not found or expired.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
