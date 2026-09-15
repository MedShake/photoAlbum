from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from photoalbum.models import Photo

from .settings import (
    AlbumStructureSettings,
    PageInstance,
)


class PlanItemKind(str, Enum):
    SPECIAL_PAGE = "special_page"
    YEAR_DIVIDER = "year_divider"
    MONTH_DIVIDER = "month_divider"
    PHOTO_GROUP = "photo_group"


@dataclass(frozen=True)
class PlanItem:
    kind: PlanItemKind
    template_id: str

    year: int | None = None
    month: int | None = None
    photos: tuple[Photo, ...] = ()

    # Configurable page occurrence.
    # Used notably by special pages.
    page_instance: PageInstance | None = None


@dataclass
class AlbumPlan:
    items: list[PlanItem] = field(default_factory=list)


class AlbumPlanner:
    def plan(
        self,
        photos: list[Photo],
        settings: AlbumStructureSettings,
    ) -> AlbumPlan:
        dated_photos = [
            photo
            for photo in photos
            if photo.capture_datetime is not None
        ]

        dated_photos.sort(
            key=lambda photo: photo.capture_datetime
        )

        plan = AlbumPlan()

        self._append_special_pages(
            plan,
            settings.front_matter,
        )

        years = {
            photo.capture_datetime.year
            for photo in dated_photos
        }

        current_year: int | None = None
        current_month: int | None = None
        month_photos: list[Photo] = []

        for photo in dated_photos:
            capture_datetime = photo.capture_datetime
            assert capture_datetime is not None

            year = capture_datetime.year
            month = capture_datetime.month

            if (
                current_year is not None
                and (
                    year != current_year
                    or month != current_month
                )
            ):
                self._append_photo_group(
                    plan,
                    current_year,
                    current_month,
                    month_photos,
                    settings,
                )
                month_photos = []

            if year != current_year:
                if settings.should_use_year_dividers(years):
                    plan.items.append(
                        PlanItem(
                            kind=PlanItemKind.YEAR_DIVIDER,
                            template_id=(
                                settings.year_dividers.template_id
                            ),
                            year=year,
                            page_instance=(
                                settings.year_dividers.page
                            ),
                        )
                    )

                current_year = year
                current_month = None

            if month != current_month:
                if settings.month_dividers.enabled:
                    plan.items.append(
                        PlanItem(
                            kind=PlanItemKind.MONTH_DIVIDER,
                            template_id=(
                                settings.month_dividers.template_id
                            ),
                            year=year,
                            month=month,
                        )
                    )

                current_month = month

            month_photos.append(photo)

        if month_photos:
            assert current_year is not None
            assert current_month is not None

            self._append_photo_group(
                plan,
                current_year,
                current_month,
                month_photos,
                settings,
            )

        self._append_special_pages(
            plan,
            settings.back_matter,
        )

        return plan

    @staticmethod
    def _append_photo_group(
        plan: AlbumPlan,
        year: int,
        month: int | None,
        photos: list[Photo],
        settings: AlbumStructureSettings,
    ) -> None:
        assert month is not None

        plan.items.append(
            PlanItem(
                kind=PlanItemKind.PHOTO_GROUP,
                template_id=settings.photo_pages.template_id,
                year=year,
                month=month,
                photos=tuple(photos),
            )
        )

    @staticmethod
    def _append_special_pages(
        plan: AlbumPlan,
        pages,
    ) -> None:
        for page in pages:
            plan.items.append(
                PlanItem(
                    kind=PlanItemKind.SPECIAL_PAGE,
                    template_id=page.template_id,
                    page_instance=page,
                )
            )

