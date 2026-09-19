import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QScrollArea

from photoalbum.album import PageFormat, PageInstance
from photoalbum.gui.page_instance_dialog import PageInstanceDialog
from photoalbum.i18n import Translator
from photoalbum.template_engine import register_discovered_template_extensions


@pytest.mark.parametrize("template", [
    "photo-page-1", "year-photo-scatter", "month-divider-classic",
    "month-divider-simple", "year-divider-classic", "calendar-index",
    "geographic-word-cloud", "dedication", "simplex-full-photo-cover",
])
@pytest.mark.parametrize("dimensions", [(180.0, 240.0), (240.0, 180.0)])
def test_settings_preview_uses_physical_geometry_and_shared_compact_layout(template, dimensions):
    app = QApplication.instance() or QApplication([])
    register_discovered_template_extensions()
    # Deliberately use the same label for different nonstandard dimensions.
    page_format = PageFormat("Custom", *dimensions)
    dialog = PageInstanceDialog(
        PageInstance(template_id=template), [], translator=Translator("en"),
        page_format=page_format,
    )
    try:
        dialog.show()
        app.processEvents()
        editor = dialog._editor
        preview = getattr(editor, "_preview_label", getattr(editor, "_preview", None))
        assert abs(preview.height() - preview.width() * dimensions[1] / dimensions[0]) <= 1
        panel_layout = preview.parentWidget().layout()
        title = panel_layout.itemAt(0).widget()
        assert 0 <= preview.y() - (title.y() + title.height()) <= 12
        assert editor.findChild(QScrollArea) is not None
        position = preview.mapTo(dialog, QPoint())
        assert position.x() >= 0 and position.y() >= 0
        assert position.x() + preview.width() <= dialog.width()
        assert position.y() + preview.height() <= dialog.height()
        available = dialog.screen().availableGeometry()
        assert dialog.width() <= round(available.width() * 0.9)
        assert dialog.height() <= round(available.height() * 0.9)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
