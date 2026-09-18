import inspect

from photoalbum.template_engine import (
    register_discovered_template_extensions,
    template_extension_registry,
)


EXPECTED_PARAMETERS = {
    "painter",
    "instance",
    "photos",
    "target_rect",
    "width",
    "height",
    "translator",
    "render_service",
    "set_waiting_key",
    "font_pixel_size",
    "page_width_mm",
    "page_height_mm",
    "album_pages",
    "composition",
    "thumbnail_cache",
    "pixel_rect",
}


def test_widget_renderers_follow_common_contract():
    register_discovered_template_extensions()

    for extension in (
        template_extension_registry
        ._extensions
        .values()
    ):
        renderer = extension.widget_renderer

        if renderer is None:
            continue

        parameters = set(
            inspect.signature(
                renderer.paint
            ).parameters
        )

        assert (
            EXPECTED_PARAMETERS
            <= parameters
        ), (
            f"{extension.template_id}: "
            f"missing "
            f"{EXPECTED_PARAMETERS - parameters}"
        )


def test_photo_renderer_accepts_qrect_pixel_geometry():
    """Album preview uses integer QRect geometry."""
    from PySide6.QtCore import QRect, QSize
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from photoalbum.templates.msb.photo_page.widget_renderer import (
        PhotoPageWidgetRenderer,
    )

    class Rect:
        x = 0.0
        y = 0.0
        width = 1.0
        height = 1.0

    class Slot:
        image_rect = Rect()

    class Cache:
        received_size = None

        @classmethod
        def load(cls, path, size):
            cls.received_size = size
            return QPixmap(20, 20)

    class Translator:
        @staticmethod
        def tr(key):
            return key

    target = QPixmap(100, 100)
    target.fill()

    from PySide6.QtGui import QPainter
    painter = QPainter(target)
    try:
        PhotoPageWidgetRenderer._paint_photo(
            painter,
            Slot(),
            "unused.jpg",
            translator=Translator(),
            thumbnail_cache=Cache(),
            pixel_rect=lambda rect: QRect(0, 0, 80, 60),
        )
    finally:
        painter.end()

    assert isinstance(Cache.received_size, QSize)
    assert Cache.received_size == QSize(80, 60)


def test_photo_renderer_accepts_qrectf_pixel_geometry():
    """Settings preview may use floating QRectF geometry."""
    from PySide6.QtCore import QRectF, QSize
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from photoalbum.templates.msb.photo_page.widget_renderer import (
        PhotoPageWidgetRenderer,
    )

    class Rect:
        x = 0.0
        y = 0.0
        width = 1.0
        height = 1.0

    class Slot:
        image_rect = Rect()

    class Cache:
        received_size = None

        @classmethod
        def load(cls, path, size):
            cls.received_size = size
            return QPixmap(20, 20)

    class Translator:
        @staticmethod
        def tr(key):
            return key

    target = QPixmap(100, 100)
    target.fill()

    painter = QPainter(target)
    try:
        PhotoPageWidgetRenderer._paint_photo(
            painter,
            Slot(),
            "unused.jpg",
            translator=Translator(),
            thumbnail_cache=Cache(),
            pixel_rect=lambda rect: QRectF(
                0.0,
                0.0,
                80.0,
                60.0,
            ),
        )
    finally:
        painter.end()

    assert isinstance(Cache.received_size, QSize)
    assert Cache.received_size == QSize(80, 60)
