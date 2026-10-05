from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from photoalbum.models import Photo

from .models import CoverPosition


class TemplateKind(str, Enum):
    COVER = "cover"
    PHOTO_PAGE = "photo_page"
    MONTH_DIVIDER = "month_divider"
    DAY_DIVIDER = "day_divider"
    YEAR_DIVIDER = "year_divider"
    SPECIAL_PAGE = "special_page"
    BODY_SPECIAL_PAGE = "body_special_page"


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


@dataclass(frozen=True)
class AutomaticPhotoPageModeDefinition:
    """Pack-owned strategy which resolves to a concrete photo-page template."""

    mode_id: str
    name: str
    pack_id: str
    pack_name: str
    template_ids: tuple[str, ...]
    settings_template_id: str
    selector_reference: str | None = None
    localized_names: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.mode_id:
            raise ValueError("Automatic photo-page mode ID cannot be empty.")
        if not self.name:
            raise ValueError("Automatic photo-page mode name cannot be empty.")
        if not self.pack_id:
            raise ValueError("Automatic photo-page mode must belong to a pack.")
        if not self.template_ids:
            raise ValueError("Automatic photo-page mode must allow at least one template.")
        if len(set(self.template_ids)) != len(self.template_ids):
            raise ValueError("Automatic photo-page mode templates must be distinct.")
        if self.settings_template_id not in self.template_ids:
            raise ValueError("Automatic mode settings template must be an allowed template.")


@dataclass(frozen=True)
class AutomaticPhotoPageContext:
    """Pagination-safe inputs exposed to a pack-owned selector."""

    photos: tuple[Photo, ...]
    page_width_mm: float
    page_height_mm: float


class TemplateRegistry:
    def __init__(
        self,
        templates: list[TemplateDefinition] | None = None,
    ) -> None:
        self._templates: dict[str, TemplateDefinition] = {}
        self._automatic_photo_page_modes: dict[
            str, AutomaticPhotoPageModeDefinition
        ] = {}
        self.pack_defaults: dict[str, dict[str, str]] = {}

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
        if template.template_id in self._automatic_photo_page_modes:
            raise ValueError(
                "Template conflicts with automatic photo-page mode: "
                f"{template.template_id}"
            )

        self._templates[template.template_id] = template

    def register_automatic_photo_page_mode(
        self,
        mode: AutomaticPhotoPageModeDefinition,
    ) -> None:
        if mode.mode_id in self._automatic_photo_page_modes:
            raise ValueError(
                "Automatic photo-page mode is already registered: "
                f"{mode.mode_id}"
            )
        if mode.mode_id in self._templates:
            raise ValueError(
                f"Automatic photo-page mode conflicts with template: {mode.mode_id}"
            )
        for template_id in mode.template_ids:
            try:
                template = self.get(template_id)
            except KeyError:
                raise ValueError(
                    f"Automatic mode {mode.mode_id!r} references unknown template "
                    f"{template_id!r}."
                ) from None
            if not template.supports(TemplateKind.PHOTO_PAGE):
                raise ValueError(
                    f"Automatic mode {mode.mode_id!r} references non-photo-page "
                    f"template {template_id!r}."
                )
            if template.pack_id != mode.pack_id:
                raise ValueError(
                    f"Automatic mode {mode.mode_id!r} cannot reference template "
                    f"{template_id!r} from another pack."
                )
        self._automatic_photo_page_modes[mode.mode_id] = mode

    def get_automatic_photo_page_mode(
        self,
        mode_id: str,
    ) -> AutomaticPhotoPageModeDefinition:
        try:
            return self._automatic_photo_page_modes[mode_id]
        except KeyError:
            raise KeyError(f"Unknown automatic photo-page mode: {mode_id}") from None

    def list_automatic_photo_page_modes(
        self,
    ) -> list[AutomaticPhotoPageModeDefinition]:
        return list(self._automatic_photo_page_modes.values())

    def automatic_photo_page_modes_for_page(
        self,
        width_mm: float,
        height_mm: float,
    ) -> list[AutomaticPhotoPageModeDefinition]:
        return [
            mode
            for mode in self._automatic_photo_page_modes.values()
            if all(
                self.get(template_id).is_compatible_with_page(width_mm, height_mm)
                for template_id in mode.template_ids
            )
        ]

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
