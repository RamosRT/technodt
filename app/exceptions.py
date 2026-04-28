from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base for domain errors mapped to JSON {detail, code}."""
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, detail: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class BarcodeError(AppError):
    status_code = 400
    code = "barcode_invalid"


class DocumentNotInOneC(AppError):
    status_code = 404
    code = "document_not_in_1c"


class OneCUnavailable(AppError):
    status_code = 502
    code = "1c_unavailable"


class EnvelopeNotFound(AppError):
    status_code = 404
    code = "envelope_not_found"


class EnvelopeNotDraft(AppError):
    status_code = 409
    code = "envelope_not_draft"


class DocumentAlreadyInEnvelope(AppError):
    status_code = 409
    code = "document_already_in_envelope"


class VerificationUnscanned(AppError):
    status_code = 409
    code = "verification_unscanned"


class InvalidSealPayload(AppError):
    status_code = 400
    code = "invalid_seal_payload"


class AdminTokenInvalid(AppError):
    status_code = 401
    code = "admin_token_invalid"


class OperatorRequired(AppError):
    status_code = 401
    code = "operator_required"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})
