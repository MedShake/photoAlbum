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


def test_incompatible_special_pages_remain_saved_but_leave_rendered_album():
    from dataclasses import replace
    from PySide6.QtWidgets import QLabel, QPushButton
    from photoalbum.album import AlbumBuilder, PageInstance, album_settings_from_json, album_settings_to_json

    widget = create_widget()
    calendar = PageInstance(template_id="calendar-index", settings={"calendar_index": {"show_title": False}})
    blank = PageInstance(template_id="blank")
    original = replace(widget.settings(), front_matter=[calendar, blank], back_matter=[blank, calendar])
    widget.set_settings(original)
    builder = AlbumBuilder(widget._registry)
    notifications = []
    widget.settings_changed.connect(lambda: notifications.append(True))

    widget._page_format_combo.setCurrentIndex(
        widget._page_format_combo.findData("custom")
    )

    for width, height, expected, enabled in [
        (179.0, 180.0, [blank, blank], False),
        (180.0, 180.0, [calendar, blank, blank, calendar], True),
    ]:
        notifications.clear()
        widget._custom_width_spin.setValue(width)
        widget._custom_height_spin.setValue(height)
        widget._custom_apply_button.click()
        assert len(notifications) == 1
        saved = widget.settings()
        assert saved.front_matter == original.front_matter
        assert saved.back_matter == original.back_matter
        restored = album_settings_from_json(album_settings_to_json(saved))
        result = builder.build([], restored)
        assert [item.page_instance for item in result.plan.items] == expected
        assert [page.page_instance for page in result.pagination.pages] == expected
        for view, index in [(widget._front_matter_list, 0), (widget._back_matter_list, 1)]:
            assert view.count() == 2
            row = view.itemWidget(view.item(index))
            assert row.findChild(QPushButton).isEnabled() == enabled
            assert ("⚠" in row.findChild(QLabel).text()) == (not enabled)
        # Reopening the project must retain the disabled selection too.
        notifications.clear()
        widget.set_settings(restored)
        assert notifications == []
        row = widget._front_matter_list.itemWidget(widget._front_matter_list.item(0))
        assert row.findChild(QPushButton).isEnabled() == enabled
    widget.close()


def test_custom_format_applies_once_and_loads_without_notifications():
    widget = create_widget()
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("custom"))
    assert not widget._orientation_combo.isEnabled()
    assert not widget._custom_format_controls.isHidden()
    changes = []
    widget.settings_changed.connect(lambda: changes.append(widget.settings()))
    widget._custom_width_spin.setValue(345.5)
    widget._custom_height_spin.setValue(123.25)
    assert changes == []
    assert widget._page_geometry() == (210.0, 297.0)
    widget._custom_apply_button.click()
    assert len(changes) == 1
    assert widget._page_geometry() == (345.5, 123.25)
    saved = widget.settings()
    page = saved.effective_page_format()
    assert (page.width_mm, page.height_mm) == (345.5, 123.25)
    widget._custom_apply_button.click()
    assert len(changes) == 1
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("a4"))
    assert widget._orientation_combo.isEnabled()
    assert widget._custom_format_controls.isHidden()
    changes.clear()
    widget.set_settings(saved)
    assert changes == []
    assert widget.settings() == saved
    assert widget._custom_width_spin.value() == 345.5
    assert widget._custom_height_spin.value() == 123.25
    widget.close()


def test_custom_format_controls_are_translated():
    from photoalbum.i18n import Translator

    app = QApplication.instance() or QApplication([])
    for language, custom, apply, width, height in [
        ("fr", "Personnalisé", "Appliquer", "Largeur", "Hauteur"),
        ("en", "Custom", "Apply", "Width", "Height"),
    ]:
        widget = AlbumSettingsWidget(create_template_registry(), translator=Translator(language))
        assert widget._page_format_combo.itemText(widget._page_format_combo.findData("custom")) == custom
        assert widget._custom_apply_button.text() == apply
        form = widget._custom_format_controls.layout()
        assert form.itemAt(0).widget().text() == width
        assert form.itemAt(2).widget().text() == height
        widget.close()


def test_custom_minimum_and_small_page_template_filtering():
    widget = create_widget()
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("custom"))
    for spin in (widget._custom_width_spin, widget._custom_height_spin):
        assert spin.minimum() == 50
        spin.setValue(20)
        assert spin.value() == 50
    widget._custom_apply_button.click()
    assert widget._month_divider_combo.findData("month-divider-classic") == -1
    assert widget._year_divider_combo.findData("calendar-index") == -1
    widget._custom_width_spin.setValue(130)
    widget._custom_height_spin.setValue(145)
    widget._custom_apply_button.click()
    assert widget._month_divider_combo.findData("month-divider-classic") >= 0
    widget._custom_width_spin.setValue(180)
    widget._custom_height_spin.setValue(180)
    widget._custom_apply_button.click()
    assert widget._year_divider_combo.findData("calendar-index") >= 0
    widget.show()
    QApplication.processEvents()
    controls = (widget._custom_width_spin, widget._custom_height_spin, widget._custom_apply_button)
    assert max(control.geometry().center().y() for control in controls) - min(
        control.geometry().center().y() for control in controls
    ) <= 1
    widget.close()


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
    from dataclasses import replace
    from photoalbum.album import PageConstraints, TemplateRegistry

    widget = create_widget()
    widget._registry = TemplateRegistry([
        replace(template, page_constraints=PageConstraints(max_width_mm=250))
        for template in widget._registry.list_all()
    ])

    # Synthetic bounds exclude widths above 250 mm, including Letter landscape.
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
        target = widget._page_geometry()
        for cover in settings.covers.values():
            assert widget._registry.get(cover.template_id).is_compatible_with_page(*target)
        assert widget._registry.get(settings.photo_pages.template_id).is_compatible_with_page(*target)
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


def test_format_change_preserves_landscape_in_one_transaction():
    from photoalbum.album import PageOrientation

    widget = create_widget()
    widget._orientation_combo.setCurrentIndex(widget._orientation_combo.findData("landscape"))
    changed = []
    widget.settings_changed.connect(lambda: changed.append(widget.settings()))
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("us-letter"))
    assert len(changed) == 1
    assert changed[0].orientation == PageOrientation.LANDSCAPE
    for cover in changed[0].covers.values():
        assert widget._registry.get(cover.template_id).is_compatible_with_page(*widget._page_geometry())
    widget.close()


def test_gui_filters_using_central_physical_compatibility(monkeypatch):
    from photoalbum.album import PageConstraints, TemplateDefinition, TemplateKind

    widget = create_widget()
    template = TemplateDefinition(
        "bounded-photo", "Bounded photo", frozenset({TemplateKind.PHOTO_PAGE}),
        photo_capacity=1, page_constraints=PageConstraints(max_width_mm=250),
    )
    widget._registry.register(template)
    calls = []
    original = TemplateDefinition.is_compatible_with_page

    def checked(self, width, height):
        if self.template_id == template.template_id:
            calls.append((width, height))
        return original(self, width, height)

    monkeypatch.setattr(TemplateDefinition, "is_compatible_with_page", checked)
    widget._refresh_template_choices()
    index = widget._photo_page_combo.findData(template.template_id)
    assert index >= 0
    widget._photo_page_combo.setCurrentIndex(index)
    notifications = []
    widget.settings_changed.connect(lambda: notifications.append(widget.settings()))
    widget._orientation_combo.setCurrentIndex(widget._orientation_combo.findData("landscape"))
    assert len(notifications) == 1
    assert widget._photo_page_combo.findData(template.template_id) == -1
    assert (210.0, 297.0) in calls and (297.0, 210.0) in calls
    widget.close()
