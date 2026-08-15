import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import _, parse_accept_language, reset_current_locale, set_current_locale
from app.core.response import error_response

logger = logging.getLogger(__name__)


VALIDATION_ERROR_KEYS = {
    "missing": "validation.required",
    "string_too_short": "validation.string_too_short",
    "string_too_long": "validation.string_too_long",
    "string_pattern_mismatch": "validation.string_pattern_mismatch",
    "greater_than": "validation.greater_than",
    "greater_than_equal": "validation.greater_than_equal",
    "less_than": "validation.less_than",
    "less_than_equal": "validation.less_than_equal",
    "int_parsing": "validation.invalid",
    "float_parsing": "validation.invalid",
    "bool_parsing": "validation.invalid",
    "date_from_datetime_parsing": "validation.invalid",
    "date_from_datetime_inexact": "validation.invalid",
    "uuid_parsing": "validation.invalid",
}


def _localize_validation_error(error: dict) -> dict:
    localized_error = dict(error)
    error_key = VALIDATION_ERROR_KEYS.get(error.get("type"), "validation.invalid")
    context = error.get("ctx") or {}
    localized_error["msg"] = _(error_key, **context)
    return localized_error


def _localized_headers(locale: str, headers: dict | None = None) -> dict:
    localized_headers = dict(headers or {})
    localized_headers["Content-Language"] = locale
    return localized_headers


def _localize_http_exception_detail(detail) -> tuple[str, str | dict, dict]:
    if isinstance(detail, str):
        return detail, detail, {}

    if isinstance(detail, dict) and isinstance(detail.get("key"), str):
        params = detail.get("params")
        return detail["key"], detail["key"], params if isinstance(params, dict) else {}

    return "common.request_error", detail, {}


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        locale = parse_accept_language(request.headers.get("Accept-Language"))
        token = set_current_locale(locale)
        try:
            msg_key, detail, params = _localize_http_exception_detail(exc.detail)
            headers = _localized_headers(locale, getattr(exc, "headers", None))
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response(message=msg_key, detail=detail, **params),
                headers=headers,
            )
        finally:
            reset_current_locale(token)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        locale = parse_accept_language(request.headers.get("Accept-Language"))
        token = set_current_locale(locale)
        try:
            errors = [_localize_validation_error(error) for error in exc.errors()]
            messages = []
            for err in errors:
                loc_parts = [str(x) for x in err.get("loc", []) if str(x) not in ("body", "query", "path")]
                loc = " -> ".join(loc_parts)
                message = err["msg"]
                messages.append(f"{loc}: {message}" if loc else message)

            invalid_data_label = _("common.invalid_data")
            formatted_message = (
                f"{invalid_data_label}: " + "; ".join(messages) if messages else _("common.invalid_request_data")
            )

            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response(message=formatted_message, detail=errors),
                headers=_localized_headers(locale),
            )
        finally:
            reset_current_locale(token)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        locale = parse_accept_language(request.headers.get("Accept-Language"))
        token = set_current_locale(locale)
        try:
            logger.error(f"Erro não tratado na requisição {request.url.path}: {exc}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response(message="common.internal_error", detail="common.internal_error"),
                headers=_localized_headers(locale),
            )
        finally:
            reset_current_locale(token)
