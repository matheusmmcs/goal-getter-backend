import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.core.exceptions import setup_exception_handlers
from app.core.i18n import parse_accept_language, reset_current_locale, set_current_locale


BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = BACKEND_ROOT / "app" / "i18n" / "locales"


def flatten_catalog(catalog: dict, prefix: str = "") -> dict[str, str]:
    flattened = {}
    for key, value in catalog.items():
        key_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(flatten_catalog(value, key_path))
        else:
            flattened[key_path] = value
    return flattened


def create_test_app() -> FastAPI:
    app = FastAPI()
    setup_exception_handlers(app)

    @app.middleware("http")
    async def i18n_middleware(request: Request, call_next):
        locale = parse_accept_language(request.headers.get("Accept-Language"))
        token = set_current_locale(locale)
        try:
            response = await call_next(request)
            response.headers["Content-Language"] = locale
            return response
        finally:
            reset_current_locale(token)

    @app.get("/validated")
    def validated(value: int):
        return {"value": value}

    @app.get("/fails")
    def fails():
        raise RuntimeError("internal diagnostic must not be public")

    @app.get("/parameterized-error")
    def parameterized_error():
        raise HTTPException(
            status_code=400,
            detail={
                "key": "daily_item.window_closed",
                "params": {"time": "17:30"},
            },
        )

    return app


def test_validation_errors_follow_request_locale():
    client = TestClient(create_test_app())

    response = client.get(
        "/validated",
        params={"value": "invalid"},
        headers={"Accept-Language": "en-US"},
    )

    assert response.status_code == 422
    assert response.headers["Content-Language"] == "en-US"
    assert response.json()["message"] == "Invalid data: value: Invalid value"
    assert response.json()["detail"][0]["msg"] == "Invalid value"


def test_unhandled_errors_do_not_expose_exception_details():
    client = TestClient(create_test_app(), raise_server_exceptions=False)

    response = client.get("/fails", headers={"Accept-Language": "en-US"})

    assert response.status_code == 500
    assert response.headers["Content-Language"] == "en-US"
    assert response.json()["detail"] == "An internal server error occurred. Please try again later."
    assert "internal diagnostic" not in response.text


def test_parameterized_http_exception_detail_is_localized():
    client = TestClient(create_test_app())

    response = client.get("/parameterized-error", headers={"Accept-Language": "en-US"})

    assert response.status_code == 400
    assert response.headers["Content-Language"] == "en-US"
    assert response.json()["message"] == "Submission window ended at 17:30 and late submissions are not allowed"
    assert response.json()["detail"] == response.json()["message"]


def test_catalogs_have_matching_keys_and_placeholders():
    catalogs = {
        locale: flatten_catalog(json.loads((LOCALES_DIR / f"{locale}.json").read_text()))
        for locale in ("pt-BR", "en-US")
    }

    assert catalogs["pt-BR"].keys() == catalogs["en-US"].keys()
    placeholder_pattern = re.compile(r"{([^{}]+)}")
    for key in catalogs["pt-BR"]:
        pt_placeholders = set(placeholder_pattern.findall(catalogs["pt-BR"][key]))
        en_placeholders = set(placeholder_pattern.findall(catalogs["en-US"][key]))
        assert pt_placeholders == en_placeholders, key


def test_static_backend_translation_keys_exist_in_catalog():
    catalog_keys = set(flatten_catalog(json.loads((LOCALES_DIR / "pt-BR.json").read_text())))
    source = "\n".join(
        path.read_text()
        for path in (BACKEND_ROOT / "app").rglob("*.py")
        if path.name != "i18n.py"
    )
    key_pattern = re.compile(r'(?:detail|message|key)\s*[:=]\s*["\']([a-z_]+(?:\.[a-z_]+)+)["\']')
    referenced_keys = set(key_pattern.findall(source))

    assert referenced_keys <= catalog_keys
    assert catalog_keys <= {key for key in catalog_keys if key in source}