from __future__ import annotations

from photoalbum.album import AutomaticPhotoPageModeDefinition, TemplateDefinition
from photoalbum.i18n import Translator
from photoalbum.template_engine.translations import translator_for_pack, translator_for_template


def _base_display_name(
    definition: TemplateDefinition | AutomaticPhotoPageModeDefinition,
    translator: Translator,
    key: str,
) -> str:
    """Keep legacy manifest names, then use catalogs and the English fallback."""
    provider_name = definition.localized_names.get(
        translator.language
    )

    if provider_name:
        return provider_name

    provider_english = definition.localized_names.get("en")

    if provider_english:
        return provider_english

    translated = translator.tr(key)

    if translated != key:
        return translated

    return definition.name


def template_display_name(
    template: TemplateDefinition,
    translator,
) -> str:
    name = _base_display_name(
        template,
        translator_for_template(template.template_id, translator),
        f"template.{template.template_id}",
    )

    if template.pack_name:
        return f"{template.pack_name} — {name}"

    return name


def automatic_photo_page_mode_display_name(
    mode: AutomaticPhotoPageModeDefinition,
    translator: Translator,
) -> str:
    name = _base_display_name(
        mode,
        translator_for_pack(mode.pack_id, translator),
        f"template.{mode.mode_id}",
    )
    return f"{mode.pack_name} — {name}" if mode.pack_name else name
