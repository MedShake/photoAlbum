from __future__ import annotations

from dataclasses import dataclass, replace

from photoalbum.models import Photo, PhotoUsage

from .pagination import PaginationEngine, PaginationResult
from .planning import AlbumPlan, AlbumPlanner
from .print_diagnostics import (
    PrintConstraints,
    PrintDiagnostic,
    PrintDiagnostics,
)
from .settings import AlbumStructureSettings, PageInstance
from .templates import TemplateRegistry
from .validation import AlbumSettingsValidator


@dataclass(frozen=True)
class AlbumBuildResult:
    plan: AlbumPlan
    pagination: PaginationResult
    print_diagnostic: PrintDiagnostic
    excluded_special_pages: tuple[PageInstance, ...] = ()
    album_photos: tuple[Photo, ...] | None = None
    excluded_photo_overrides: tuple[PageInstance, ...] = ()

    @property
    def template_photos(self) -> tuple[Photo, ...]:
        if self.album_photos is not None:
            return self.album_photos
        # Compatibility for callers constructing a build result directly.
        return tuple({photo.identity: photo for item in self.plan.items
                      for photo in item.photos if photo.usage != PhotoUsage.OFF}.values())

    # pagination.pages contains the physical interior pages
    # of the album. Covers are rendered separately and are
    # therefore not part of PaginationResult.
    COVER_PAGE_COUNT = 4

    @property
    def interior_page_count(self) -> int:
        return len(self.pagination.pages)

    @property
    def total_page_count(self) -> int:
        return (
            self.interior_page_count
            + self.COVER_PAGE_COUNT
        )


class AlbumBuilder:
    def __init__(
        self,
        registry: TemplateRegistry,
    ) -> None:
        self._registry = registry

    def build(
        self,
        photos: list[Photo],
        settings: AlbumStructureSettings,
        *,
        print_constraints: PrintConstraints | None = None,
    ) -> AlbumBuildResult:
        AlbumSettingsValidator(
            self._registry
        ).validate(settings)

        # Keep saved selections intact; only the effective album omits pages
        # that cannot fit the current physical geometry.
        page_format = settings.effective_page_format()
        excluded_special_pages = []
        excluded_photo_overrides = []
        album_photos = tuple(photo for photo in photos if photo.usage != PhotoUsage.OFF)

        def compatible(page):
            accepted = self._registry.get(page.template_id).is_compatible_with_page(
                page_format.width_mm, page_format.height_mm,
            )
            if not accepted:
                excluded_special_pages.append(page)
            return accepted

        settings = replace(
            settings,
            front_matter=[page for page in settings.front_matter if compatible(page)],
            back_matter=[page for page in settings.back_matter if compatible(page)],
            body_insertions=[item for item in settings.body_insertions
                             if item.enabled and compatible(item.page)],
        )
        for override in settings.photo_page_overrides:
            if not self._registry.get(override.page.template_id).is_compatible_with_page(
                page_format.width_mm, page_format.height_mm
            ):
                excluded_photo_overrides.append(override.page)
        settings = replace(settings, photo_page_overrides=[
            replace(item, page=settings.photo_pages.page)
            if item.page in excluded_photo_overrides else item
            for item in settings.photo_page_overrides
        ])

        plan = AlbumPlanner().plan(
            list(album_photos),
            settings,
        )

        pagination = PaginationEngine(
            self._registry
        ).paginate(
            plan,
            settings,
        )

        print_diagnostic = PrintDiagnostics().analyze(
            pagination,
            print_constraints,
        )

        return AlbumBuildResult(
            plan=plan,
            pagination=pagination,
            print_diagnostic=print_diagnostic,
            excluded_special_pages=tuple(excluded_special_pages),
            excluded_photo_overrides=tuple(excluded_photo_overrides),
            album_photos=album_photos,
        )
