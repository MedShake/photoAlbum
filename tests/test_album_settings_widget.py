from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
)
from photoalbum.template_engine import create_template_registry

from photoalbum.gui.widgets import AlbumSettingsWidget


def create_widget() -> AlbumSettingsWidget:
    application = QApplication.instance()

    if application is None:
        QApplication([])

    return AlbumSettingsWidget(
        create_template_registry()
    )


def test_default_photo_template_is_two_photos():
    widget = create_widget()

    settings = widget.settings()

    assert (
        settings.photo_pages.template_id
        == "photo-page-2"
    )


def test_default_month_dividers_are_enabled():
    widget = create_widget()

    settings = widget.settings()

    assert settings.month_dividers.enabled
    assert (
        settings.month_dividers.placement
        == DividerPlacement.RIGHT_PAGE
    )


def test_year_divider_is_available_for_one_year():
    widget = create_widget()

    widget.set_available_years({2025})

    settings = widget.settings()

    assert settings.year_dividers.enabled
    assert widget._year_dividers_checkbox.isEnabled()

def test_year_dividers_are_used_for_one_year():
    widget = create_widget()

    widget.set_available_years({2025})

    settings = widget.settings()

    assert settings.year_dividers.enabled
    assert settings.should_use_year_dividers({2025})

def test_year_dividers_are_available_for_multiple_years():
    widget = create_widget()

    widget.set_available_years(
        {2025, 2026}
    )

    settings = widget.settings()

    assert settings.year_dividers.enabled


def test_a4_landscape_is_available():
    widget = create_widget()

    widget._refresh_orientation_availability()

    model = widget._orientation_combo.model()
    item = model.item(1)

    assert item.isEnabled()
    assert item.text() == "Landscape"
    assert item.toolTip() == ""


def test_letter_landscape_unavailable_label_is_translated():
    widget = create_widget()

    # A4 is the default first format. Select US Letter,
    # whose landscape target is intentionally unavailable.
    for index in range(widget._page_format_combo.count()):
        if widget._page_format_combo.itemData(index) == "us-letter":
            widget._page_format_combo.setCurrentIndex(index)
            break
    else:
        raise AssertionError("US Letter format not found")

    widget._refresh_orientation_availability()

    model = widget._orientation_combo.model()
    item = model.item(1)

    assert not item.isEnabled()
    assert item.text() == (
        "Landscape — templates unavailable for this orientation"
    )



def test_settings_can_be_restored():
    widget = create_widget()

    original = AlbumStructureSettings(
        covers={
            CoverPosition.FRONT: CoverSettings(
                position=CoverPosition.FRONT,
                template_id="year-photo-scatter",
            ),
            CoverPosition.INSIDE_FRONT: CoverSettings(
                position=CoverPosition.INSIDE_FRONT,
                template_id="geographic-word-cloud",
            ),
            CoverPosition.INSIDE_BACK: CoverSettings(
                position=CoverPosition.INSIDE_BACK,
                template_id="calendar-index",
            ),
            CoverPosition.BACK: CoverSettings(
                position=CoverPosition.BACK,
                template_id="geographic-word-cloud",
            ),
        },
        month_dividers=DividerSettings(
            enabled=False,
            template_id="month-divider-classic",
            placement=DividerPlacement.NATURAL,
        ),
        year_dividers=DividerSettings(
            enabled=True,
            template_id="year-divider-classic",
            placement=DividerPlacement.RIGHT_PAGE,
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-page-4",
        ),
        front_matter=[
            SpecialPage(
                template_id="calendar-index"
            ),
        ],
        back_matter=[
            SpecialPage(
                template_id="dedication"
            ),
        ],
    )

    widget.set_available_years(
        {2025, 2026}
    )
    widget.set_settings(original)

    assert widget.settings() == original


def test_target_changes_emit_once_with_compatible_selections():
    widget = create_widget()
    snapshots = []
    widget.settings_changed.connect(lambda: snapshots.append(widget.settings()))
    for combo, value in [
        (widget._orientation_combo, "landscape"),
        (widget._orientation_combo, "portrait"),
        (widget._page_format_combo, "us-letter"),
        (widget._page_format_combo, "a4"),
    ]:
        snapshots.clear()
        combo.setCurrentIndex(combo.findData(value))
        assert len(snapshots) == 1
        settings = snapshots[0]
        target = widget._target()
        for cover in settings.covers.values():
            assert widget._registry.get(cover.template_id).supports_target(target)
        assert widget._registry.get(settings.photo_pages.template_id).supports_target(target)
    widget.close()


def test_loading_landscape_settings_does_not_emit_or_discard_local_options():
    from dataclasses import replace
    from photoalbum.album import PageOrientation, PageInstance

    widget = create_widget()
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("us-letter"))
    original = widget.settings()
    photo_page = PageInstance(template_id="photo-page-1", settings={"custom": "preserve"})
    settings = replace(original, page_format="a4", orientation=PageOrientation.LANDSCAPE,
                       photo_pages=PhotoPageSettings(page=photo_page))
    notifications = []
    widget.settings_changed.connect(lambda: notifications.append(True))
    widget.set_settings(settings)
    assert notifications == []
    restored = widget.settings()
    assert restored.page_format == "a4"
    assert restored.orientation == PageOrientation.LANDSCAPE
    assert restored.photo_pages.page == photo_page
    assert not widget._loading_settings
    widget.close()


def test_format_change_selects_supported_orientation_in_one_transaction():
    from photoalbum.album import PageOrientation

    widget = create_widget()
    widget._orientation_combo.setCurrentIndex(widget._orientation_combo.findData("landscape"))
    changed = []
    widget.settings_changed.connect(lambda: changed.append(widget.settings()))
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("us-letter"))
    assert len(changed) == 1
    assert changed[0].orientation == PageOrientation.PORTRAIT
    for cover in changed[0].covers.values():
        assert widget._registry.get(cover.template_id).supports_target(widget._target())
    widget.close()
