"""Generic, pack-owned translation catalogs."""
from __future__ import annotations

import json
from pathlib import Path


def load_pack_catalogs(pack_path: Path) -> dict[str, dict[str, str]]:
    directory = pack_path / "i18n"
    if not directory.is_dir():
        return {}
    catalogs = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in data.items()
        ):
            raise ValueError(f"Invalid template pack catalog: {path}")
        catalogs[path.stem.lower()] = data
    return catalogs


class PackTranslator:
    """Overlay pack translations on an application translator."""

    def __init__(self, base, catalogs: dict[str, dict[str, str]]) -> None:
        self._base = base
        self._catalogs = catalogs

    @property
    def language(self) -> str:
        return self._base.language

    def set_language(self, language: str) -> None:
        self._base.set_language(language)

    def tr(self, key: str, **values) -> str:
        language = str(self.language or "en").lower()
        language = language.split("-", 1)[0].split("_", 1)[0]
        text = self._catalogs.get(language, {}).get(key)
        if text is None:
            text = self._catalogs.get("en", {}).get(key)
        if text is None:
            return self._base.tr(key, **values)
        return text.format(**values)

    def month_name(self, month: int) -> str:
        return self._base.month_name(month)


_PACK_CATALOGS: dict[str, dict[str, dict[str, str]]] = {}
_TEMPLATE_PACKS: dict[str, str] = {}


def replace_registered_pack_catalogs(
    pack_catalogs: dict[str, dict[str, dict[str, str]]],
    template_packs: dict[str, str],
) -> None:
    global _PACK_CATALOGS, _TEMPLATE_PACKS
    _PACK_CATALOGS, _TEMPLATE_PACKS = pack_catalogs, template_packs


def translator_for_pack(pack_id: str, base):
    catalogs = _PACK_CATALOGS.get(pack_id)
    return PackTranslator(base, catalogs) if catalogs else base


def translator_for_template(template_id: str, base):
    pack_id = _TEMPLATE_PACKS.get(template_id)
    return translator_for_pack(pack_id, base) if pack_id else base
