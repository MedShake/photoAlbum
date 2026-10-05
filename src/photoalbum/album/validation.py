from __future__ import annotations

from .settings import AlbumStructureSettings
from .templates import TemplateKind, TemplateRegistry


class AlbumSettingsValidator:
    def __init__(
        self,
        registry: TemplateRegistry,
    ) -> None:
        self._registry = registry

    def validate(
        self,
        settings: AlbumStructureSettings,
    ) -> None:
        from photoalbum.template_engine.instances import validate_template_instance

        instances = [cover.page for cover in settings.covers.values()]
        instances.extend((settings.month_dividers.page, settings.year_dividers.page,
                          settings.day_dividers.page,
                          settings.photo_pages.page))
        instances.extend(settings.front_matter)
        instances.extend(settings.back_matter)
        instances.extend(item.page for item in settings.photo_page_overrides)
        instances.extend(item.page for item in settings.body_insertions)
        anchors = [item.photo_identity for item in settings.photo_page_overrides]
        if len(set(anchors)) != len(anchors) or any(not anchor for anchor in anchors):
            raise ValueError("Photo page overrides need distinct nonempty photo identities.")
        for item in settings.photo_page_overrides:
            self._require_kind(item.page.template_id, TemplateKind.PHOTO_PAGE)
        for item in settings.body_insertions:
            self._require_kind(item.page.template_id, TemplateKind.BODY_SPECIAL_PAGE)
        for instance in instances:
            validate_template_instance(instance)

        for cover in settings.covers.values():
            self._require_kind(
                cover.template_id,
                TemplateKind.COVER,
            )

        self._require_kind(
            settings.month_dividers.template_id,
            TemplateKind.MONTH_DIVIDER,
        )

        self._require_kind(
            settings.year_dividers.template_id,
            TemplateKind.YEAR_DIVIDER,
        )

        self._require_kind(
            settings.day_dividers.template_id,
            TemplateKind.DAY_DIVIDER,
        )

        self._require_kind(
            settings.photo_pages.template_id,
            TemplateKind.PHOTO_PAGE,
        )

        for page in settings.front_matter:
            self._require_kind(
                page.template_id,
                TemplateKind.SPECIAL_PAGE,
            )

        for page in settings.back_matter:
            self._require_kind(
                page.template_id,
                TemplateKind.SPECIAL_PAGE,
            )

    def _require_kind(
        self,
        template_id: str,
        expected_kind: TemplateKind,
    ) -> None:
        template = self._registry.get(template_id)

        if not template.supports(expected_kind):
            raise ValueError(
                f"Template {template_id!r} cannot be used as "
                f"{expected_kind.value!r}."
            )
