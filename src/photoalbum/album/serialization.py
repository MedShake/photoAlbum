from __future__ import annotations

import json

from .models import CoverPosition
from .settings import (
    AlbumStructureSettings,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
)


def album_settings_to_json(
    settings: AlbumStructureSettings,
) -> str:
    data = {
        "covers": {
            position.value: {
                "template_id": cover.template_id,
            }
            for position, cover in settings.covers.items()
        },
        "month_dividers": {
            "enabled": settings.month_dividers.enabled,
            "template_id": settings.month_dividers.template_id,
            "placement": settings.month_dividers.placement.value,
        },
        "year_dividers": {
            "enabled": settings.year_dividers.enabled,
            "template_id": settings.year_dividers.template_id,
            "placement": settings.year_dividers.placement.value,
        },
        "photo_pages": {
            "template_id": settings.photo_pages.template_id,
        },
        "front_matter": [
            {
                "template_id": page.template_id,
            }
            for page in settings.front_matter
        ],
        "back_matter": [
            {
                "template_id": page.template_id,
            }
            for page in settings.back_matter
        ],
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
    )


def album_settings_from_json(
    value: str,
) -> AlbumStructureSettings:
    data = json.loads(value)

    covers = {
        position: CoverSettings(
            position=position,
            template_id=data["covers"][position.value][
                "template_id"
            ],
        )
        for position in CoverPosition
    }

    month_data = data["month_dividers"]
    year_data = data["year_dividers"]
    photo_data = data["photo_pages"]

    return AlbumStructureSettings(
        covers=covers,
        month_dividers=DividerSettings(
            enabled=bool(month_data["enabled"]),
            template_id=month_data["template_id"],
            placement=DividerPlacement(
                month_data["placement"]
            ),
        ),
        year_dividers=DividerSettings(
            enabled=bool(year_data["enabled"]),
            template_id=year_data["template_id"],
            placement=DividerPlacement(
                year_data["placement"]
            ),
        ),
        photo_pages=PhotoPageSettings(
            template_id=photo_data["template_id"],
        ),
        front_matter=[
            SpecialPage(
                template_id=item["template_id"]
            )
            for item in data.get(
                "front_matter",
                [],
            )
        ],
        back_matter=[
            SpecialPage(
                template_id=item["template_id"]
            )
            for item in data.get(
                "back_matter",
                [],
            )
        ],
    )

