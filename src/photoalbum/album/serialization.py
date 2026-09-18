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
    PhotoCaptionSettings,
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


def _divider_instance_from_data(
    data: dict,
) -> PageInstance:
    page_data = data.get("page")

    if isinstance(page_data, dict):
        return _instance_from_data(
            page_data
        )

    # Projects written before divider pages became
    # independent PageInstance objects.
    return PageInstance(
        template_id=str(
            data["template_id"]
        )
    )


def album_settings_to_json(
    settings: AlbumStructureSettings,
) -> str:
    data = {
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
            "caption": {
                "show_datetime": (
                    settings.photo_pages.caption.show_datetime
                ),
                "show_location": (
                    settings.photo_pages.caption.show_location
                ),
            },
        },

        "page_numbers": {
            "enabled": settings.page_numbers.enabled,
        },

        "page_format": settings.page_format,
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
    caption_data = photo_data["caption"]
    page_number_data = data["page_numbers"]
    print_data = data["print_settings"]

    return AlbumStructureSettings(
        covers=covers,

        month_dividers=DividerSettings(
            enabled=bool(
                month_data["enabled"]
            ),
            page=_divider_instance_from_data(
                month_data
            ),
            placement=DividerPlacement(
                month_data["placement"]
            ),
        ),

        year_dividers=DividerSettings(
            enabled=bool(
                year_data["enabled"]
            ),
            page=_divider_instance_from_data(
                year_data
            ),
            placement=DividerPlacement(
                year_data["placement"]
            ),
        ),

        photo_pages=PhotoPageSettings(
            page=(
                _instance_from_data(
                    photo_data["page"]
                )
                if isinstance(
                    photo_data.get("page"),
                    dict,
                )
                else PageInstance(
                    template_id=str(
                        photo_data["template_id"]
                    )
                )
            ),
            caption=PhotoCaptionSettings(
                show_datetime=bool(
                    caption_data["show_datetime"]
                ),
                show_location=bool(
                    caption_data["show_location"]
                ),
            ),
        ),

        page_numbers=PageNumberSettings(
            enabled=bool(
                page_number_data["enabled"]
            ),
        ),

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
