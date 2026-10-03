"""Domain errors and the user-facing error envelope.

Technical infrastructure details are logged, never returned to the client.
"""

from typing import Any


class AppError(Exception):
    """An error that is safe to show to the user."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class UnsupportedFile(AppError):
    status_code = 415
    code = "unsupported_file"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


def error_body(code: str, message: str, request_id: str | None, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details is not None:
        body["error"]["details"] = details
    return body
