from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TemplateKind(str, Enum):
    COVER = "cover"
    PHOTO_PAGE = "photo_page"
    MONTH_DIVIDER = "month_divider"
    YEAR_DIVIDER = "year_divider"
    SPECIAL_PAGE = "special_page"


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    name: str
    allowed_kinds: frozenset[TemplateKind]
    photo_capacity: int = 0

    # Optional translations supplied by the template provider.
    # template_id remains the stable technical identifier.
    localized_names: dict[str, str] = field(
        default_factory=dict
    )
    localized_descriptions: dict[str, str] = field(
        default_factory=dict
    )

    def display_name(
        self,
        language: str,
    ) -> str:
        return (
            self.localized_names.get(language)
            or self.localized_names.get("en")
            or self.name
        )

    def display_description(
        self,
        language: str,
    ) -> str | None:
        return (
            self.localized_descriptions.get(language)
            or self.localized_descriptions.get("en")
        )

    def __post_init__(self) -> None:
        if not self.template_id:
            raise ValueError("Template ID cannot be empty.")

        if not self.name:
            raise ValueError("Template name cannot be empty.")

        if not self.allowed_kinds:
            raise ValueError(
                "Template must allow at least one usage kind."
            )

        if self.photo_capacity < 0:
            raise ValueError(
                "Photo capacity cannot be negative."
            )

        allows_photo_pages = (
            TemplateKind.PHOTO_PAGE
            in self.allowed_kinds
        )

        if allows_photo_pages and self.photo_capacity == 0:
            raise ValueError(
                "A template usable as a photo page must expose "
                "at least one photo slot."
            )

        if (
            not allows_photo_pages
            and self.photo_capacity != 0
        ):
            raise ValueError(
                "Only templates usable as photo pages may expose "
                "photo slots."
            )

    def supports(
        self,
        kind: TemplateKind,
    ) -> bool:
        return kind in self.allowed_kinds


class TemplateRegistry:
    def __init__(
        self,
        templates: list[TemplateDefinition] | None = None,
    ) -> None:
        self._templates: dict[str, TemplateDefinition] = {}

        for template in templates or []:
            self.register(template)

    def register(
        self,
        template: TemplateDefinition,
    ) -> None:
        if template.template_id in self._templates:
            raise ValueError(
                "Template is already registered: "
                f"{template.template_id}"
            )

        self._templates[template.template_id] = template

    def get(
        self,
        template_id: str,
    ) -> TemplateDefinition:
        try:
            return self._templates[template_id]
        except KeyError:
            raise KeyError(
                f"Unknown template: {template_id}"
            ) from None

    def list_all(self) -> list[TemplateDefinition]:
        return list(self._templates.values())

    def list_by_kind(
        self,
        kind: TemplateKind,
    ) -> list[TemplateDefinition]:
        return [
            template
            for template in self._templates.values()
            if template.supports(kind)
        ]