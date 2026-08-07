from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel
from app.core.i18n import _

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    detail: Optional[Any] = None


def success_response(data: Any = None, message: str = "common.success", **kwargs) -> dict:
    return {
        "success": True,
        "message": _(message, **kwargs),
        "data": data,
        "detail": None,
    }


def error_response(message: str = "common.request_error", detail: Any = None, **kwargs) -> dict:
    translated_message = _(message, **kwargs)
    translated_detail = _(detail) if isinstance(detail, str) else detail
    return {
        "success": False,
        "message": translated_message,
        "data": None,
        "detail": translated_detail,
    }
