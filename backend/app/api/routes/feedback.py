from fastapi import APIRouter, Response, status

from app.api.deps import ClientIdDep, SessionDep
from app.db.repositories import FeedbackRepository
from app.schemas.common import ErrorResponse
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    operation_id="submitFeedback",
    summary="Rate an assistant response (👍/👎). Re-submitting updates the rating.",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": FeedbackResponse, "description": "Existing rating updated"},
        422: {"model": ErrorResponse},
    },
)
async def submit_feedback(
    payload: FeedbackRequest, response: Response, session: SessionDep, client_id: ClientIdDep
) -> FeedbackResponse:
    row, created = await FeedbackRepository(session).upsert(
        client_id=client_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
        capability=payload.capability,
        model=payload.model,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return FeedbackResponse(
        id=row.id,
        message_id=row.message_id,
        rating=row.rating,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
