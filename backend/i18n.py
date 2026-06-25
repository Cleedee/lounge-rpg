import json
import os
import logging

logger = logging.getLogger("neon_scratch.i18n")

_translations: dict[str, str] = {}
_current_locale = "en-US"


def load_locale(locale: str, locale_dir: str | None = None) -> None:
    global _translations, _current_locale
    _current_locale = locale
    if locale == "en-US":
        _translations = {}
        return
    if locale_dir is None:
        locale_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
    path = os.path.join(locale_dir, f"{locale}.json")
    if not os.path.exists(path):
        logger.warning("locale file not found: %s, falling back to en-US", path)
        _translations = {}
        _current_locale = "en-US"
        return
    with open(path, encoding="utf-8") as f:
        _translations = json.load(f)
    logger.info("loaded locale %s (%d keys)", locale, len(_translations))


def t(key: str, default: str = "", **kwargs) -> str:
    val = _translations.get(key, default or key)
    if kwargs:
        val = val.format(**kwargs)
    return val


def locale() -> str:
    return _current_locale


def is_pt_br() -> bool:
    return _current_locale == "pt-BR"
