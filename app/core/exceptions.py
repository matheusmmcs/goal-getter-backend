import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import _
from app.core.response import error_response

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        msg_key = detail if isinstance(detail, str) else "common.request_error"
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=msg_key, detail=detail),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        messages = []
        for err in errors:
            loc_parts = [str(x) for x in err.get("loc", []) if str(x) not in ("body", "query", "path")]
            loc = " -> ".join(loc_parts)
            msg = err.get("msg", "Valor inválido")
            translated_msg = _(msg)
            messages.append(f"{loc}: {translated_msg}" if loc else translated_msg)

        invalid_data_label = _("common.invalid_data")
        formatted_message = (
            f"{invalid_data_label}: " + "; ".join(messages) if messages else _("common.invalid_request_data")
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(message=formatted_message, detail=errors),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Erro não tratado na requisição {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(message="common.internal_error", detail=str(exc)),
        )
