"""i18n.py — internationalization manager with language-change signal."""

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class I18nManager(QObject):
    """Loads locale JSON files and provides translation lookup.

    Emits language_changed when the language switches, so pages/widgets
    can re-translate themselves.
    """

    language_changed = Signal(str)

    def __init__(self, locales_dir: Path, default_language: str = "zh"):
        super().__init__()
        self._locales_dir = Path(locales_dir)
        self._language = default_language
        self._translations: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        for lang in ("zh", "en"):
            path = self._locales_dir / f"{lang}.json"
            if path.exists():
                self._translations[lang] = json.loads(
                    path.read_text("utf-8")
                )

    def t(self, key: str, **kwargs) -> str:
        """Return translated string for the current language.

        Walks dotted keys: t('nav.chat') → translations['zh']['nav']['chat'].
        Falls back to the key itself if not found.
        Formats with **kwargs via str.format().
        """
        trans = self._translations.get(self._language, {})
        for part in key.split("."):
            if isinstance(trans, dict):
                trans = trans.get(part, key)
            else:
                return key
        if isinstance(trans, dict):
            return key
        result = str(trans)
        if kwargs:
            try:
                result = result.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return result

    def set_language(self, lang: str):
        if lang != self._language and lang in self._translations:
            self._language = lang
            self.language_changed.emit(lang)

    @property
    def language(self) -> str:
        return self._language

    @property
    def available_languages(self) -> list[str]:
        return list(self._translations.keys())
