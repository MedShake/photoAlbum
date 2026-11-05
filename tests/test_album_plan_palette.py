"""Plan appearance follows the native item delegate, without color overrides."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QEnterEvent, QImage, QPainter, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QLabel, QStyle, QStyleFactory, QStyleOptionViewItem, QToolButton,
)

from photoalbum.album import BodyPageInsertion, ContentAnchor, CoverPosition, PageInstance
from tests.test_album_plan_widget import create_result, create_structure_settings, create_widget


@pytest.fixture(params=[name for name in QStyleFactory.keys()
                        if name.lower() in {"fusion", "windows", "windowsvista", "windows11"}])
def app(request):
    app = QApplication.instance() or QApplication([])
    old_style, old_palette = app.style().objectName(), app.palette()
    app.setStyle(request.param)
    yield app
    app.setStyle(old_style)
    app.setPalette(old_palette)
    app.processEvents()


def plan_palette(dark):
    palette = QPalette()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        palette.setColor(group, QPalette.Window, QColor("#282828" if dark else "#eeeeee"))
        palette.setColor(group, QPalette.WindowText, QColor("#eeeeee" if dark else "#161616"))
        palette.setColor(group, QPalette.Base, QColor("#181818" if dark else "#ffffff"))
        palette.setColor(group, QPalette.Text, QColor("#eeeeee" if dark else "#161616"))
        palette.setColor(group, QPalette.Highlight, QColor("#305b90"))
        palette.setColor(group, QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#999999"))
    palette.setColor(QPalette.Inactive, QPalette.Text, QColor("#dddddd" if dark else "#303030"))
    return palette


def items(tree):
    def walk(item):
        yield item
        for index in range(item.childCount()):
            yield from walk(item.child(index))
    for index in range(tree.topLevelItemCount()):
        yield from walk(tree.topLevelItem(index))


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def plan(app, request, show_active_window):
    app.setPalette(plan_palette(request.param))
    widget = create_widget()
    settings = create_structure_settings()
    settings.body_insertions = [
        BodyPageInsertion(ContentAnchor("photo", photo_identity="missing"), PageInstance("blank"), enabled)
        for enabled in (False, True)
    ]
    widget.set_result(create_result(), settings)
    widget.resize(1500, 650)
    show_active_window(widget)
    yield widget, settings, request.param
    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)
    app.processEvents()


def assert_native_colors(tree):
    for item in items(tree):
        for column in range(tree.columnCount()):
            assert item.data(column, Qt.ItemDataRole.ForegroundRole) is None
            assert item.data(column, Qt.ItemDataRole.BackgroundRole) is None


def test_native_hover_selection_focus_and_palette_changes(plan, app):
    widget, _, dark = plan
    tree = widget._tree
    first = tree.topLevelItem(0)
    second = tree.topLevelItem(1)
    tree.setFocus(Qt.FocusReason.TabFocusReason)
    tree.setCurrentItem(first)
    app.processEvents()
    assert tree.hasFocus()
    assert tree.selectedItems() == [first]
    point = tree.visualItemRect(second).center()
    QTest.mouseMove(tree.viewport(), point)
    app.processEvents()
    assert_native_colors(tree)
    assert tree.selectedItems() == [first]
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert tree.currentItem() is second
    assert tree.selectedItems() == [second]
    QTest.keyClick(tree, Qt.Key.Key_Up)
    assert tree.currentItem() is first
    app.setPalette(plan_palette(not dark))
    app.processEvents()
    assert tree.palette().color(QPalette.Text) == plan_palette(not dark).color(QPalette.Text)
    assert tree.hasFocus()
    assert tree.selectedItems() == [first]
    tree.setEnabled(False)
    assert tree.palette().currentColorGroup() == QPalette.Disabled
    assert_native_colors(tree)
    tree.setEnabled(True)
    assert tree.selectedItems() == [first]


def test_diagnostic_text_uses_native_palette_for_all_item_states(plan):
    widget, _, _ = plan
    tree = widget._tree
    item = next(item for item in items(tree) if "unused slot" in item.text(5))
    index = tree.indexFromItem(item, 5)
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        for selected in (False, True):
            option = QStyleOptionViewItem()
            option.initFrom(tree)
            option.rect = QRect(0, 0, 300, 28)
            option.state = QStyle.StateFlag.State_Enabled if group != QPalette.Disabled else QStyle.StateFlag.State_None
            if group == QPalette.Active:
                option.state |= QStyle.StateFlag.State_Active
            if selected:
                option.state |= QStyle.StateFlag.State_Selected
            option.palette = tree.palette()
            image = QImage(option.rect.size(), QImage.Format.Format_ARGB32)
            image.fill(option.palette.color(group, QPalette.Base))
            painter = QPainter(image)
            try:
                tree.itemDelegate().paint(painter, option, index)
            finally:
                painter.end()
            role = QPalette.HighlightedText if selected else QPalette.Text
            expected = option.palette.color(group, role)
            # Allow small native-font antialiasing differences.
            assert any(max(abs(a - b) for a, b in zip(image.pixelColor(x, y).getRgb()[:3], expected.getRgb()[:3])) <= 16
                       for y in range(4, image.height() - 4) for x in range(4, 160))


def test_inactive_insertions_remain_selectable_and_can_be_reenabled(plan):
    widget, settings, _ = plan
    tree = widget._tree
    disabled = next(item for item in items(tree) if item.text(5) == "Disabled")
    dormant = next(item for item in items(tree) if item.text(5) == "Inactive anchor or incompatible page format")
    for item in (disabled, dormant):
        assert item.flags() & Qt.ItemFlag.ItemIsEnabled
        assert item.flags() & Qt.ItemFlag.ItemIsSelectable
    tree.setCurrentItem(disabled)
    assert tree.selectedItems() == [disabled]
    actions = tree.itemWidget(disabled, 3).findChildren(QToolButton)
    emitted = []
    widget.settings_changed.connect(emitted.append)
    assert actions[1].toolTip() == "Enable"
    actions[1].click()
    assert len(emitted) == 1
    assert emitted[0].body_insertions[0].enabled
    assert emitted[0].body_insertions[0].page is settings.body_insertions[0].page
    assert not settings.body_insertions[0].enabled
    assert_native_colors(tree)


def test_preview_hover_still_opens_and_closes_preview(plan, app):
    widget, _, _ = plan
    widget._preview_widget = SimpleNamespace(
        create_cover_preview=lambda settings, position, **kwargs: QLabel("Paper preview", kwargs["parent"]),
    )
    icon, (item, _, _) = next((icon, target) for icon, target in widget._preview_hover_items.items()
                             if target[2] == CoverPosition.FRONT)
    point = QPointF(1, 1)
    QApplication.sendEvent(icon, QEnterEvent(point, point, QPointF(icon.mapToGlobal(QPoint(1, 1)))))
    assert widget._page_preview_timer.isActive()
    assert widget._pending_page_preview[0] is item
    widget._show_pending_page_preview()
    popup = widget._page_preview_popup
    assert popup is not None and popup.isVisible()
    assert popup.findChild(QLabel).text() == "Paper preview"
    QApplication.sendEvent(icon, QEvent(QEvent.Type.Leave))
    assert widget._page_preview_popup is None
    assert not popup.isVisible()
    assert not widget._page_preview_timer.isActive()
    assert_native_colors(widget._tree)
