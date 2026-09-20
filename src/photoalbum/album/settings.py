from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from math import isfinite

from .models import CoverPosition, PageFormat, page_format_from_id, oriented_page_format


class PageOrientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class DividerPlacement(str, Enum):
    NATURAL = "natural"
    RIGHT_PAGE = "right_page"
    RIGHT_PAGE_WITH_BLANK_FACING = (
        "right_page_with_blank_facing"
    )


@dataclass(frozen=True)
class CoverScatterSettings:
    seeds: tuple[int, ...] = (0,)
    selected_seed_index: int = 0

    @property
    def seed(self) -> int:
        if not self.seeds:
            return 0

        return self.seeds[
            min(
                max(self.selected_seed_index, 0),
                len(self.seeds) - 1,
            )
        ]


@dataclass(frozen=True)
class PageInstance:
    template_id: str

    instance_id: str = field(
        default_factory=lambda: uuid4().hex
    )

    # JSON-compatible template-specific settings.
    settings: dict[str, object] = field(
        default_factory=dict
    )

    def with_settings(
        self,
        settings: dict[str, object],
    ) -> "PageInstance":
        return PageInstance(
            template_id=self.template_id,
            instance_id=self.instance_id,
            settings=dict(settings),
        )


def scatter_settings_from_instance(
    instance: PageInstance,
) -> CoverScatterSettings:
    data = instance.settings.get("scatter", {})

    if not isinstance(data, dict):
        data = {}

    seeds = tuple(
        int(value)
        for value in data.get("seeds", [0])
    ) or (0,)

    return CoverScatterSettings(
        seeds=seeds,
        selected_seed_index=int(
            data.get(
                "selected_seed_index",
                0,
            )
        ),
    )


def instance_with_scatter_settings(
    instance: PageInstance,
    scatter: CoverScatterSettings,
) -> PageInstance:
    settings = dict(instance.settings)

    settings["scatter"] = {
        "seeds": list(scatter.seeds),
        "selected_seed_index": (
            scatter.selected_seed_index
        ),
    }

    return instance.with_settings(settings)


@dataclass(frozen=True, init=False)
class CoverSettings:
    position: CoverPosition
    page: PageInstance

    def __init__(
        self,
        position: CoverPosition,
        template_id: str | None = None,
        *,
        page: PageInstance | None = None,
        scatter: CoverScatterSettings | None = None,
    ) -> None:
        if page is None:
            if template_id is None:
                raise ValueError(
                    "template_id or page is required"
                )

            page = PageInstance(
                template_id=template_id,
            )

            if scatter is not None:
                page = instance_with_scatter_settings(
                    page,
                    scatter,
                )

        object.__setattr__(
            self,
            "position",
            position,
        )
        object.__setattr__(
            self,
            "page",
            page,
        )

    @property
    def template_id(self) -> str:
        return self.page.template_id

    @property
    def instance_id(self) -> str:
        return self.page.instance_id

    @property
    def scatter(self) -> CoverScatterSettings:
        return scatter_settings_from_instance(
            self.page
        )


# A special page is now a real independent page occurrence.
SpecialPage = PageInstance


@dataclass(frozen=True, init=False)
class DividerSettings:
    enabled: bool
    page: PageInstance
    placement: DividerPlacement

    def __init__(
        self,
        enabled: bool,
        template_id: str | None = None,
        placement: DividerPlacement = DividerPlacement.RIGHT_PAGE,
        *,
        page: PageInstance | None = None,
    ) -> None:
        if page is None:
            if template_id is None:
                raise ValueError(
                    "template_id or page is required"
                )

            page = PageInstance(
                template_id=template_id,
            )

        object.__setattr__(
            self,
            "enabled",
            enabled,
        )
        object.__setattr__(
            self,
            "page",
            page,
        )
        object.__setattr__(
            self,
            "placement",
            placement,
        )

    @property
    def template_id(self) -> str:
        return self.page.template_id

    @property
    def instance_id(self) -> str:
        return self.page.instance_id


@dataclass(frozen=True)
class PhotoCaptionSettings:
    show_datetime: bool = True
    show_location: bool = True


@dataclass(frozen=True, init=False)
class PhotoPageSettings:
    page: PageInstance
    caption: PhotoCaptionSettings

    def __init__(
        self,
        template_id: str | None = None,
        caption: PhotoCaptionSettings | None = None,
        *,
        page: PageInstance | None = None,
    ) -> None:
        if page is None:
            if template_id is None:
                raise ValueError(
                    "template_id or page is required"
                )

            page = PageInstance(
                template_id=template_id
            )

        if caption is None:
            caption = PhotoCaptionSettings()

        object.__setattr__(
            self,
            "page",
            page,
        )
        object.__setattr__(
            self,
            "caption",
            caption,
        )

    @property
    def template_id(self) -> str:
        return self.page.template_id

    @property
    def instance_id(self) -> str:
        return self.page.instance_id


@dataclass(frozen=True)
class PageNumberSettings:
    enabled: bool = True


@dataclass(frozen=True)
class PrintSettings:
    # None means no page-count constraint.
    page_multiple: int | None = None


@dataclass
class AlbumStructureSettings:
    covers: dict[CoverPosition, CoverSettings]

    month_dividers: DividerSettings
    year_dividers: DividerSettings

    photo_pages: PhotoPageSettings

    page_format: str = "a4"
    orientation: PageOrientation = PageOrientation.PORTRAIT

    page_numbers: PageNumberSettings = field(
        default_factory=PageNumberSettings
    )

    print_settings: PrintSettings = field(
        default_factory=PrintSettings
    )

    front_matter: list[SpecialPage] = field(
        default_factory=list
    )
    back_matter: list[SpecialPage] = field(
        default_factory=list
    )

    # Complete project-persisted settings owned by template packs.
    #
    # This deliberately lives at album/project level rather than inside
    # one PageInstance: several pages may depend on the same pack theme.
    template_pack_settings: dict[str, object] = field(
        default_factory=dict
    )

    custom_width_mm: float = 210.0
    custom_height_mm: float = 297.0

    def effective_page_format(self) -> PageFormat:
        """Resolve host choices; custom dimensions are already oriented."""
        if self.page_format == "custom":
            dimensions = (self.custom_width_mm, self.custom_height_mm)
            if any(not isfinite(value) or value <= 0 for value in dimensions):
                raise ValueError("Custom page dimensions must be positive and finite.")
            return PageFormat("Custom", *dimensions)
        return oriented_page_format(page_format_from_id(self.page_format), self.orientation)

    def year_dividers_available(
        self,
        years: set[int],
    ) -> bool:
        return bool(years)

    def should_use_year_dividers(
        self,
        years: set[int],
    ) -> bool:
        return (
            self.year_dividers.enabled
            and self.year_dividers_available(years)
        )