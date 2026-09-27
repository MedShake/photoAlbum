from __future__ import annotations

from copy import copy

from PySide6.QtGui import QPixmap

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.template_engine.preview_backend import (
    PreviewJob,
    TemplatePreviewBackend,
)

from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
)

from .composition import eligible_photos
from .rendering import render_options
from .render_worker import GeographicMapRenderWorker
from .defaults import (
    DEFAULT_BORDER_COLOR,
    DEFAULT_LAND_COLOR,
    DEFAULT_MARKER_MODE,
    DEFAULT_POINT_COLOR,
    DEFAULT_POINT_COLOR_MODE,
    DEFAULT_POINT_OPACITY,
    DEFAULT_POINT_SIZE,
    DEFAULT_PROJECTION,
    DEFAULT_WATER_COLOR,
)


class GeographicMapPreviewBackend(
    TemplatePreviewBackend
):
    template_id = "geographic-map"

    @staticmethod
    def _settings(
        instance: PageInstance,
    ) -> dict:
        settings = instance.settings.get(
            "geographic_map",
            {},
        )

        if not isinstance(settings, dict):
            return {}

        return settings

    def effective_photos(
        self,
        instance: PageInstance,
        photos,
    ) -> tuple:
        return tuple(eligible_photos(photos, self._settings(instance).get("year")))

    def photo_signature(
        self,
        photo,
    ) -> object:
        return (
            photo.filename,
            photo.capture_datetime,
            photo.width,
            photo.height,
            photo.orientation,
            photo.latitude,
            photo.longitude,
        )

    def render_settings_signature(
        self,
        instance: PageInstance,
        *,
        template_pack_settings=None,
    ) -> object:
        settings = self._settings(instance)

        theme = msb_theme_from_pack_settings(
            template_pack_settings or {}
        )

        month_colors = tuple(
            (
                month,
                tuple(theme.color_for_month(month)),
            )
            for month in range(1, 13)
        )

        return (
            "year",
            settings.get("year"),
            "projection",
            settings.get(
                "projection",
                DEFAULT_PROJECTION,
            ),
            "land_color",
            settings.get(
                "land_color",
                DEFAULT_LAND_COLOR,
            ),
            "water_color",
            settings.get(
                "water_color",
                DEFAULT_WATER_COLOR,
            ),
            "border_color",
            settings.get(
                "border_color",
                DEFAULT_BORDER_COLOR,
            ),
            "marker_mode",
            settings.get(
                "marker_mode",
                DEFAULT_MARKER_MODE,
            ),
            "point_color_mode",
            settings.get(
                "point_color_mode",
                DEFAULT_POINT_COLOR_MODE,
            ),
            "point_color",
            settings.get(
                "point_color",
                DEFAULT_POINT_COLOR,
            ),
            "point_size",
            settings.get(
                "point_size",
                DEFAULT_POINT_SIZE,
            ),
            "point_opacity",
            settings.get(
                "point_opacity",
                DEFAULT_POINT_OPACITY,
            ),
            "show_month_legend",
            bool(
                settings.get(
                    "show_month_legend",
                    True,
                )
            ),
            "month_colors",
            month_colors,
            "legend_font_family",
            theme.default_font_family,
        )

    def create_job(
        self,
        *,
        request_id: str,
        instance: PageInstance,
        photos,
        width: int,
        height: int,
        page_width_mm: float,
        page_height_mm: float,
        translator: Translator,
        template_pack_settings=None,
    ) -> PreviewJob:
        settings = self._settings(instance)

        worker = GeographicMapRenderWorker(
            request_id=request_id,
            width=width,
            height=height,
            photos=tuple(copy(photo) for photo in photos),
            year=settings.get("year"),
            options=render_options(settings, translator, template_pack_settings),
        )

        def finalize(
            data: bytes,
        ) -> QPixmap:
            pixmap = QPixmap()

            pixmap.loadFromData(
                data
            )

            return pixmap

        return PreviewJob(
            worker=worker,
            finalize=finalize,
        )
