from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.i18n import Translator
from photoalbum.album.composition import PageComposition
from photoalbum.album.planning import PlanItemKind
from photoalbum.rendering import PageRenderGeometry, PageRenderer, RenderImageCache


class PageTemplateSettingsWidget(QWidget):
    """
    Base class for one template's settings editor.

    A template editor owns every UI decision related to its
    PageInstance. PageInstanceDialog deliberately knows
    nothing about template-specific settings.
    """

    instance_changed = Signal()

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._instance = instance
        self._photos = tuple(
            photos
        )
        self._translator = translator
        self._render_service = render_service
        self._page_format = page_format
        self._template_pack_settings = dict(
            template_pack_settings or {}
        )
        self._settings_page_renderer = PageRenderer(translator=self._translator)
        self._settings_image_cache = RenderImageCache()

    def render_composition_preview(
        self, composition, *, width: int, height: int, project_photos=(),
        album_pages=(), show_empty_slots=True, set_waiting_key=None,
    ) -> QPixmap:
        pixmap = QPixmap(max(1, int(width)), max(1, int(height)))
        pixmap.fill(Qt.GlobalColor.white)
        geometry = PageRenderGeometry(
            width=pixmap.width(), height=pixmap.height(),
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )
        painter = QPainter(pixmap)
        try:
            self._settings_page_renderer.paint(
                painter=painter, composition=composition,
                target_rect=QRect(0, 0, pixmap.width(), pixmap.height()),
                width=pixmap.width(), height=pixmap.height(),
                page_width_mm=self._page_format.width_mm,
                page_height_mm=self._page_format.height_mm,
                font_pixel_size=geometry.font_pixel_size, pixel_rect=geometry.pixel_rect,
                thumbnail_cache=self._settings_image_cache,
                project_photos=tuple(project_photos), album_pages=tuple(album_pages),
                template_pack_settings=self._template_pack_settings,
                render_service=self._render_service, set_waiting_key=set_waiting_key,
                paint_fallback=None, show_empty_slots=show_empty_slots,
            )
        finally:
            painter.end()
        return pixmap

    def render_template_preview(
        self, *, width: int, height: int, photos=(), page_attributes=None,
        album_pages=(), set_waiting_key=None,
        kind: PlanItemKind = PlanItemKind.SPECIAL_PAGE,
    ) -> QPixmap:
        attributes = dict(page_attributes or {})
        page = SimpleNamespace(
            number=int(attributes.pop("number", 1)),
            kind=kind,
            template_id=self._instance.template_id,
            page_instance=self._instance,
            photos=tuple(photos),
            **attributes,
        )
        composition = PageComposition(page=page)
        pixmap = QPixmap(max(1, int(width)), max(1, int(height)))
        pixmap.fill(Qt.GlobalColor.white)
        geometry = PageRenderGeometry(
            width=pixmap.width(), height=pixmap.height(),
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )
        painter = QPainter(pixmap)
        try:
            self._settings_page_renderer.paint(
                painter=painter, composition=composition,
                target_rect=QRect(0, 0, pixmap.width(), pixmap.height()),
                width=pixmap.width(), height=pixmap.height(),
                page_width_mm=self._page_format.width_mm,
                page_height_mm=self._page_format.height_mm,
                font_pixel_size=geometry.font_pixel_size,
                pixel_rect=geometry.pixel_rect,
                thumbnail_cache=self._settings_image_cache,
                project_photos=tuple(photos), album_pages=tuple(album_pages),
                template_pack_settings=self._template_pack_settings,
                render_service=self._render_service,
                set_waiting_key=set_waiting_key, paint_fallback=None,
                show_empty_slots=True,
            )
        finally:
            painter.end()
        return pixmap

    def instance(
        self,
    ) -> PageInstance:
        return self._instance

    def template_pack_settings(
        self,
    ) -> dict[str, object]:
        """
        Return a defensive copy of the template-pack context.

        Template editors may update pack-wide settings such as
        a shared theme. The dialog hosting the editor is
        responsible for propagating the resulting context back
        to its owner.
        """
        return dict(
            self._template_pack_settings
        )

    def set_template_pack_settings(
        self,
        settings,
    ) -> None:
        """
        Replace the editor's working template-pack context.

        Keep ownership local to the editor: callers and editors
        must not accidentally share a mutable settings dict.
        """
        self._template_pack_settings = dict(
            settings or {}
        )
