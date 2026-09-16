from __future__ import annotations

from photoalbum.album import TemplateDefinition
from photoalbum.i18n import Translator


def _base_template_display_name(
    template: TemplateDefinition,
    translator: Translator,
) -> str:
    """
    Resolve the user-facing template name.

    Priority:
    1. translation supplied by the template provider
    2. built-in application translation
    3. TemplateDefinition.name fallback
    """

    provider_name = template.localized_names.get(
        translator.language
    )

    if provider_name:
        return provider_name

    provider_english = template.localized_names.get("en")

    if provider_english:
        return provider_english

    key = f"template.{template.template_id}"
    translated = translator.tr(key)

    if translated != key:
        return translated

    return template.name


def template_display_name(
    template: TemplateDefinition,
    translator,
) -> str:
    name = _base_template_display_name(
        template,
        translator,
    )

    if template.pack_name:
        return f"{template.pack_name} — {name}"

    return name
