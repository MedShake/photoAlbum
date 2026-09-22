from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect, QSize, Signal, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.i18n import Translator
from photoalbum.album.composition import PageComposition
from photoalbum.album.planning import PlanItemKind
from photoalbum.rendering import PageRenderGeometry, PageRenderer, RenderImageCache


class _SettingsControlsArea(QScrollArea):
    """Keep large settings forms accessible without forcing a huge dialog."""

    def sizeHint(self) -> QSize:
        return self.widget().sizeHint().boundedTo(QSize(560, 600))

    def minimumSizeHint(self) -> QSize:
        return QSize(220, 120)


class PageTemplateSettingsWidget(QWidget):
    """
    Base class for one template's settings editor.

    Templates own their controls and rendering. The framework owns the
    physical preview geometry and the shared controls/preview layout.
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

    def preview_size(
        self,
        width: int,
    ) -> tuple[int, int]:
        """
        Return a UI preview size preserving the effective physical
        page aspect ratio.

        ``width`` is only an interface constraint. The height is
        derived from the physical page geometry received by this
        settings editor.
        """
        preview_width = max(1, int(width))

        page_width_mm = float(
            self._page_format.width_mm
        )
        page_height_mm = float(
            self._page_format.height_mm
        )

        if (
            page_width_mm <= 0.0
            or page_height_mm <= 0.0
        ):
            return preview_width, preview_width

        preview_height = max(
            1,
            round(
                preview_width
                * page_height_mm
                / page_width_mm
            ),
        )

        return preview_width, preview_height

    def create_preview_label(self, width: int) -> QLabel:
        # Reserve screen space for controls and the host dialog's header/footer.
        # These are UI bounds only; physical dimensions remain unchanged.
        available = self.screen().availableGeometry()
        max_width = max(120, round(available.width() * 0.9) - 360)
        max_height = max(160, round(available.height() * 0.9) - 220)
        preview_width, preview_height = self.preview_size(min(width, max_width))
        if preview_height > max_height:
            preview_width, preview_height = self.preview_size(
                max(1, int(preview_width * max_height / preview_height))
            )
        label = QLabel()
        label.setFixedSize(preview_width, preview_height)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("border: 1px solid #888; background: white;")
        return label

    def create_preview_title(self) -> QWidget:
        title = QLabel(self._translator.tr("page_settings.preview_section"))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        return title

    def add_settings_columns(self, root, controls: QWidget, preview: QLabel) -> None:
        """Place controls and a compact, top-aligned physical page preview."""
        available_width = round(self.screen().availableGeometry().width() * 0.9)
        controls_width = max(220, controls.minimumSizeHint().width())
        preview_width = min(preview.width(), max(120, available_width - controls_width - 100))
        preview.setFixedSize(*self.preview_size(preview_width))
        controls.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        controls_area = _SettingsControlsArea()
        controls_area.setFrameShape(QScrollArea.Shape.NoFrame)
        controls_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        controls_area.setWidgetResizable(True)
        controls_area.setWidget(controls)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(8)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = self.create_preview_title()
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        panel_layout.addWidget(title)
        panel_layout.addWidget(preview)
        root.addWidget(controls_area, 1)
        root.addWidget(panel, 0, Qt.AlignmentFlag.AlignTop)

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
