from __future__ import annotations

from dataclasses import dataclass
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
    kind: TemplateKind
    photo_capacity: int = 0

    def __post_init__(self) -> None:
        if not self.template_id:
            raise ValueError("Template ID cannot be empty.")

        if not self.name:
            raise ValueError("Template name cannot be empty.")

        if self.photo_capacity < 0:
            raise ValueError(
                "Photo capacity cannot be negative."
            )

        if (
            self.kind == TemplateKind.PHOTO_PAGE
            and self.photo_capacity == 0
        ):
            raise ValueError(
                "A photo page template must expose "
                "at least one photo slot."
            )

        if (
            self.kind != TemplateKind.PHOTO_PAGE
            and self.photo_capacity != 0
        ):
            raise ValueError(
                "Only photo page templates may expose "
                "photo slots."
            )


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
            if template.kind == kind
        ]

