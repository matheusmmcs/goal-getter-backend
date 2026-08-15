import json
import logging
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "pt-BR"
SUPPORTED_LOCALES = {"pt-BR", "en-US"}

_current_locale_var: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)
_translations: Dict[str, Dict[str, Any]] = {}


def load_translations() -> None:
    global _translations
    locales_dir = Path(__file__).parent.parent / "i18n" / "locales"
    _translations.clear()

    for locale in SUPPORTED_LOCALES:
        file_path = locales_dir / f"{locale}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _translations[locale] = data
            except Exception as e:
                logger.error(f"Erro ao carregar traduções para {locale}: {e}")

    logger.info(f"Traduções carregadas para os locais: {list(_translations.keys())}")


def parse_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LOCALE

    # Split header values, e.g., 'en-US,en;q=0.9,pt-BR;q=0.8'
    parts = [p.strip() for p in header.split(",")]
    for part in parts:
        lang = part.split(";")[0].strip()
        if not lang:
            continue
        # Exact match
        if lang in SUPPORTED_LOCALES:
            return lang
        # Case insensitive match
        lang_lower = lang.lower()
        if lang_lower in ("en", "en-us", "en-gb"):
            return "en-US"
        if lang_lower in ("pt", "pt-br", "pt-pt"):
            return "pt-BR"

    return DEFAULT_LOCALE


def set_current_locale(locale: str) -> Token[str]:
    valid_locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    return _current_locale_var.set(valid_locale)


def reset_current_locale(token: Token[str]) -> None:
    _current_locale_var.reset(token)


def get_current_locale() -> str:
    return _current_locale_var.get()


def translate(key: str, locale: str | None = None, **kwargs) -> str:
    target_locale = locale or get_current_locale()
    if target_locale not in SUPPORTED_LOCALES:
        target_locale = DEFAULT_LOCALE

    locale_dict = _translations.get(target_locale, {})
    
    # Traverse dotted key (e.g. 'daily_item.already_exists')
    parts = key.split(".")
    val = locale_dict
    found = True
    for part in parts:
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
            found = False
            break

    # Fallback to DEFAULT_LOCALE if key not found in requested locale
    if not found and target_locale != DEFAULT_LOCALE:
        fallback_dict = _translations.get(DEFAULT_LOCALE, {})
        val = fallback_dict
        found = True
        for part in parts:
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                found = False
                break

    if not found or not isinstance(val, str):
        # Key not found, return key formatted with kwargs if any
        try:
            return key.format(**kwargs) if kwargs else key
        except (KeyError, ValueError):
            return key

    try:
        return val.format(**kwargs) if kwargs else val
    except (KeyError, ValueError):
        return val


# Alias helper function
_ = translate

# Load translations on module import
load_translations()
