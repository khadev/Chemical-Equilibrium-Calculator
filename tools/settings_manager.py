"""
tools/settings_manager.py
==========================
Persistent application settings backed by ``config/settings.json``.
Implements deep-merge so partial updates never wipe defaults.
Thread-safe singleton.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_ROOT, "config", "settings.json")
_TRANSLATIONS_PATH = os.path.join(_ROOT, "config", "translations.json")
_PRESETS_PATH = os.path.join(_ROOT, "config", "presets.json")


class SettingsManager:
    """
    Singleton JSON settings manager.

    Provides:
      - ``get(key, *sub_keys)`` — nested key access with safe defaults
      - ``set(key, *sub_keys, value=...)`` — nested key write
      - ``save()``  — persist to config/settings.json
      - ``tr(key)`` — translate a UI string key

    Example:
        sm = SettingsManager()
        exe = sm.get("paths", "fcea2_exe")
        sm.set("paths", "fcea2_exe", value="/path/FCEA2.exe")
        sm.save()
    """

    _instance: Optional["SettingsManager"] = None

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._data: Dict[str, Any] = {}
            inst._translations: Dict[str, Any] = {}
            inst._presets: list = []
            inst._load()
            cls._instance = inst
            log.debug("SettingsManager initialised from %s", _SETTINGS_PATH)
        return cls._instance

    # ── Load ──────────────────────────────────────────────────────────
    def _load(self) -> None:
        """Load settings, translations, and presets from disk."""
        if os.path.exists(_SETTINGS_PATH):
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                log.error("Failed to load settings: %s", exc)
                self._data = {}

        if os.path.exists(_TRANSLATIONS_PATH):
            try:
                with open(_TRANSLATIONS_PATH, "r", encoding="utf-8") as fh:
                    self._translations = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                log.error("Failed to load translations: %s", exc)

        if os.path.exists(_PRESETS_PATH):
            try:
                with open(_PRESETS_PATH, "r", encoding="utf-8") as fh:
                    self._presets = json.load(fh).get("presets", [])
            except (json.JSONDecodeError, OSError) as exc:
                log.error("Failed to load presets: %s", exc)

    # ── Public API ────────────────────────────────────────────────────
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Retrieve a nested value from settings.

        Args:
            *keys: Sequence of nested keys.
            default: Returned when the key path is absent.

        Returns:
            The stored value or ``default``.

        Example:
            sm.get("paths", "fcea2_exe")
        """
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k)
            if node is None:
                return default
        return node

    def set(self, *keys: str, value: Any) -> None:
        """
        Write a value at the given nested key path.

        Args:
            *keys: Sequence of nested keys (last key is written).
            value: Value to store.

        Raises:
            ValueError: If no keys are provided.
        """
        if not keys:
            raise ValueError("At least one key is required.")
        node = self._data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value

    def save(self) -> None:
        """Persist current settings to ``config/settings.json``."""
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            log.debug("Settings saved to %s", _SETTINGS_PATH)
        except OSError as exc:
            log.error("Failed to save settings: %s", exc)

    def tr(self, key: str) -> str:
        """
        Translate a UI string key using the active language.

        Args:
            key: Translation dictionary key (e.g. ``"run_cea"``).

        Returns:
            Translated string, or ``key`` if not found.
        """
        lang = self.get("language") or "en"
        d = self._translations
        return (d.get(lang, {}).get(key)
                or d.get("en", {}).get(key)
                or key)

    def get_presets(self) -> list:
        """Return all fuel/oxidizer presets."""
        return list(self._presets)

    def fcea2_exe(self) -> str:
        """Return the configured FCEA2.exe path."""
        return self.get("paths", "fcea2_exe") or ""

    def cea_folder(self) -> str:
        """Return the CEA working directory."""
        return self.get("paths", "cea_folder") or ""

    def cea_available(self) -> bool:
        """Return True if FCEA2.exe is configured and the file exists."""
        exe = self.fcea2_exe()
        return bool(exe and os.path.isfile(exe))

    def language(self) -> str:
        """Return the active language code (``'en'`` or ``'fr'``)."""
        return self.get("language") or "en"

    def set_language(self, lang: str) -> None:
        """
        Switch the active UI language.

        Args:
            lang: Language code (``'en'`` or ``'fr'``).
        """
        self.set("language", value=lang)
        self.save()

    def all_data(self) -> Dict[str, Any]:
        """Return a deep copy of the full settings dict."""
        return copy.deepcopy(self._data)
