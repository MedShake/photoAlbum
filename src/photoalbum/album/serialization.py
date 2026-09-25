from __future__ import annotations

import json

from .models import CoverPosition
from .settings import (
    AlbumStructureSettings,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PageInstance,
    PageNumberSettings,
    PageOrientation,
    PhotoPageSettings,
    PrintSettings,
)


def _instance_to_data(
    instance: PageInstance,
) -> dict:
    return {
        "instance_id": instance.instance_id,
        "template_id": instance.template_id,
        "settings": instance.settings,
    }


def _instance_from_data(
    data: dict,
) -> PageInstance:
    return PageInstance(
        instance_id=str(data["instance_id"]),
        template_id=str(data["template_id"]),
        settings=dict(
            data.get("settings", {})
        ),
    )


def album_settings_to_json(
    settings: AlbumStructureSettings,
) -> str:
    data = {
        "schema_version": 2,
        "covers": {
            position.value: _instance_to_data(
                cover.page
            )
            for position, cover
            in settings.covers.items()
        },

        "month_dividers": {
            "enabled": settings.month_dividers.enabled,
            "page": _instance_to_data(
                settings.month_dividers.page
            ),
            "placement": (
                settings.month_dividers.placement.value
            ),
        },

        "year_dividers": {
            "enabled": settings.year_dividers.enabled,
            "page": _instance_to_data(
                settings.year_dividers.page
            ),
            "placement": (
                settings.year_dividers.placement.value
            ),
        },

        "photo_pages": {
            "page": _instance_to_data(
                settings.photo_pages.page
            ),
        },

        "page_numbers": {
            "enabled": settings.page_numbers.enabled,
        },

        "page_format": settings.page_format,
        "custom_width_mm": settings.custom_width_mm,
        "custom_height_mm": settings.custom_height_mm,
        "orientation": settings.orientation.value,

        "print_settings": {
            "page_multiple": (
                settings.print_settings.page_multiple
            ),
        },

        "front_matter": [
            _instance_to_data(page)
            for page in settings.front_matter
        ],

        "back_matter": [
            _instance_to_data(page)
            for page in settings.back_matter
        ],

        "template_pack_settings": (
            settings.template_pack_settings
        ),
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
    if data.get("schema_version") != 2:
        raise ValueError("Unsupported album settings schema; recreate this beta album's settings.")

    covers = {
        position: CoverSettings(
            position=position,
            page=_instance_from_data(
                data["covers"][position.value]
            ),
        )
        for position in CoverPosition
    }

    month_data = data["month_dividers"]
    year_data = data["year_dividers"]
    photo_data = data["photo_pages"]
    page_number_data = data["page_numbers"]
    print_data = data["print_settings"]

    return AlbumStructureSettings(
        covers=covers,

        month_dividers=DividerSettings(
            enabled=bool(
                month_data["enabled"]
            ),
            page=_instance_from_data(month_data["page"]),
            placement=DividerPlacement(
                month_data["placement"]
            ),
        ),

        year_dividers=DividerSettings(
            enabled=bool(
                year_data["enabled"]
            ),
            page=_instance_from_data(year_data["page"]),
            placement=DividerPlacement(
                year_data["placement"]
            ),
        ),

        photo_pages=PhotoPageSettings(page=_instance_from_data(photo_data["page"])),

        page_numbers=PageNumberSettings(
            enabled=bool(
                page_number_data["enabled"]
            ),
        ),

        custom_width_mm=float(data.get("custom_width_mm", 210.0)),
        custom_height_mm=float(data.get("custom_height_mm", 297.0)),
        page_format=str(
            data["page_format"]
        ),
        orientation=PageOrientation(
            data["orientation"]
        ),

        print_settings=PrintSettings(
            page_multiple=(
                print_data["page_multiple"]
            ),
        ),

        front_matter=[
            _instance_from_data(item)
            for item in data["front_matter"]
        ],

        back_matter=[
            _instance_from_data(item)
            for item in data["back_matter"]
        ],

        template_pack_settings=dict(
            data.get(
                "template_pack_settings",
                {},
            )
        ),
    )
