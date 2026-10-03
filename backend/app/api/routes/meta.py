import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import ContainerDep, SessionDep
from app.core.errors import Unauthorized
from app.db.base import utcnow
from app.db.repositories import FeedbackRepository, RequestLogRepository
from app.schemas.chat import MAX_ATTACHMENTS_PER_MESSAGE, MAX_MESSAGE_CHARS, MAX_MESSAGES
from app.schemas.common import ErrorResponse
from app.schemas.meta import (
    CapabilitiesResponse,
    CapabilityInfo,
    ChatLimits,
    HealthResponse,
    MetricsResponse,
    ToolInfo,
    UploadLimits,
)
from app.services.files import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS

router = APIRouter(tags=["meta"])

CAPABILITIES = [
    CapabilityInfo(
        id="fast",
        label="Fast",
        description="Quick answers for everyday questions and simple code.",
        supports_images=False,
    ),
    CapabilityInfo(
        id="reasoning",
        label="Reasoning",
        description="Deeper thinking for complex problems, analysis and debugging.",
        supports_images=False,
    ),
    CapabilityInfo(
        id="vision",
        label="Vision",
        description="Understands images: photos, screenshots, charts and diagrams.",
        supports_images=True,
    ),
]


@router.get(
    "/health",
    operation_id="getHealth",
    summary="Liveness/readiness probe",
    responses={503: {"model": HealthResponse, "description": "Database unavailable"}},
)
async def health(container: ContainerDep, response: Response) -> HealthResponse:
    db_ok = await container.db.ping()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=container.settings.app_version,
        environment=container.settings.app_env,
        database="ok" if db_ok else "unavailable",
        llm_provider=container.llm.name,
        search_provider=container.search.name,
    )


@router.get("/capabilities", operation_id="getCapabilities", summary="Model capabilities, tools and limits for the UI")
async def capabilities(container: ContainerDep) -> CapabilitiesResponse:
    settings = container.settings
    return CapabilitiesResponse(
        default="auto",
        capabilities=CAPABILITIES,
        tools=[ToolInfo(name=t.name, label=t.label, description=t.description) for t in container.tools.all()],
        uploads=UploadLimits(
            max_bytes=settings.upload_max_bytes,
            max_files_per_message=MAX_ATTACHMENTS_PER_MESSAGE,
            document_extensions=DOCUMENT_EXTENSIONS,
            image_extensions=IMAGE_EXTENSIONS,
            retention_hours=settings.upload_retention_hours,
        ),
        chat=ChatLimits(max_message_chars=MAX_MESSAGE_CHARS, max_messages=MAX_MESSAGES),
    )


@router.get(
    "/metrics",
    operation_id="getMetrics",
    summary="Aggregated, content-free service metrics for operations",
    responses={401: {"model": ErrorResponse}},
)
async def metrics(
    container: ContainerDep,
    session: SessionDep,
    window_minutes: Annotated[int, Query(ge=1, le=60 * 24 * 30)] = 60,
    authorization: Annotated[str | None, Header()] = None,
) -> MetricsResponse:
    token = container.settings.ops_token
    if token is None and container.settings.is_production:
        raise Unauthorized("Metrics are disabled: configure OPS_TOKEN to enable them.")
    if token is not None:
        expected = f"Bearer {token.get_secret_value()}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise Unauthorized("A valid ops token is required.")
    window = timedelta(minutes=window_minutes)
    summary = await RequestLogRepository(session).summary(window)
    feedback = await FeedbackRepository(session).counts_since(utcnow() - window)
    return MetricsResponse(window_minutes=window_minutes, feedback=feedback, **summary)
