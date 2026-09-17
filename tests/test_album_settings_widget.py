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


def test_landscape_unavailable_label_is_translated():
    widget = create_widget()

    widget._refresh_orientation_availability()

    model = widget._orientation_combo.model()
    item = model.item(1)

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