from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from .models import CoverPosition


class TemplateKind(str, Enum):
    COVER = "cover"
    PHOTO_PAGE = "photo_page"
    MONTH_DIVIDER = "month_divider"
    YEAR_DIVIDER = "year_divider"
    SPECIAL_PAGE = "special_page"


@dataclass(frozen=True)
class PageConstraints:
    """Optional inclusive physical bounds, in millimetres."""

    min_width_mm: float | None = None
    max_width_mm: float | None = None
    min_height_mm: float | None = None
    max_height_mm: float | None = None

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number or null.")
        for axis in ("width", "height"):
            minimum = getattr(self, f"min_{axis}_mm")
            maximum = getattr(self, f"max_{axis}_mm")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"Minimum {axis} exceeds maximum {axis}.")

    def accepts(self, width_mm: float, height_mm: float) -> bool:
        for value, minimum, maximum in (
            (width_mm, self.min_width_mm, self.max_width_mm),
            (height_mm, self.min_height_mm, self.max_height_mm),
        ):
            if not isfinite(value) or value <= 0:
                return False
            if minimum is not None and value < minimum:
                return False
            if maximum is not None and value > maximum:
                return False
        return True


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    name: str
    allowed_kinds: frozenset[TemplateKind]
    photo_capacity: int = 0

    pack_id: str | None = None
    pack_name: str | None = None

    page_constraints: PageConstraints = field(default_factory=PageConstraints)

    cover_positions: frozenset[CoverPosition] = field(
        default_factory=frozenset
    )

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

        allows_cover = (
            TemplateKind.COVER
            in self.allowed_kinds
        )

        if self.cover_positions and not allows_cover:
            raise ValueError(
                "Only cover templates may declare cover positions."
            )

    def supports(
        self,
        kind: TemplateKind,
    ) -> bool:
        return kind in self.allowed_kinds

    def is_compatible_with_page(self, width_mm: float, height_mm: float) -> bool:
        return self.page_constraints.accepts(width_mm, height_mm)

    def supports_cover_position(
        self,
        position: CoverPosition,
    ) -> bool:
        if not self.supports(TemplateKind.COVER):
            return False

        return (
            not self.cover_positions
            or position in self.cover_positions
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
            if template.supports(kind)
        ]

    def list_for_page(
        self,
        kind: TemplateKind,
        width_mm: float,
        height_mm: float,
    ) -> list[TemplateDefinition]:
        return [
            template
            for template in self.list_by_kind(kind)
            if template.is_compatible_with_page(width_mm, height_mm)
        ]

    def album_page_available(
        self,
        width_mm: float,
        height_mm: float,
    ) -> bool:
        """
        A target is usable when all four cover positions and at
        least one photo-page template can be rendered.

        Templates may come from different packs.
        """
        photo_pages = self.list_for_page(
            TemplateKind.PHOTO_PAGE,
            width_mm, height_mm,
        )

        if not photo_pages:
            return False

        covers = self.list_for_page(
            TemplateKind.COVER,
            width_mm, height_mm,
        )

        return all(
            any(
                template.supports_cover_position(position)
                for template in covers
            )
            for position in CoverPosition
        )
