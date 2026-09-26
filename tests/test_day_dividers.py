"""Daily separators extend monthly planning without changing disabled albums."""
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumBuilder, AlbumPlanner, AlbumSettingsValidator, CoverSettings,
    DividerPlacement, PageInstance, PageSide, PlanItemKind, TemplateKind,
)
from photoalbum.album.pagination import BlankPageReason, PaginationEngine
from photoalbum.album.serialization import album_settings_from_json, album_settings_to_json
from photoalbum.album.summary import AlbumSummaryBuilder
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.template_engine import discovery
from photoalbum.template_engine.translations import translator_for_template


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(app):
    discovery.register_discovered_template_extensions()
    widget = AlbumSettingsWidget(discovery.create_template_registry(), translator=Translator("fr"))
    yield widget
    widget.close()


def photo(name, date):
    return Photo(path=Path(name), filename=name, capture_datetime=date)


def daily_settings(widget, *, months=False, years=False):
    settings = widget.settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=True, placement=DividerPlacement.NATURAL)
    settings.month_dividers = replace(settings.month_dividers, enabled=months, placement=DividerPlacement.NATURAL)
    settings.year_dividers = replace(settings.year_dividers, enabled=years, placement=DividerPlacement.NATURAL)
    return settings


def test_daily_groups_keep_dates_order_hierarchy_and_instances(widget):
    settings = daily_settings(widget, months=True, years=True)
    settings.day_dividers = replace(settings.day_dividers, page=PageInstance(
        template_id="day-divider-simple", settings={"day_divider_simple": {"title_font_size": 36}},
    ))
    dates = [datetime(2024, 12, 31), datetime(2025, 1, 1), datetime(2025, 3, 1),
             datetime(2025, 3, 1, 23, 59), datetime(2025, 3, 2), datetime(2025, 3, 5)]
    photos = [photo(str(i), date) for i, date in enumerate(dates)]
    plan = AlbumPlanner().plan(list(reversed(photos)) + [photo("undated", None)], settings)
    Y, M, D, P = (PlanItemKind.YEAR_DIVIDER, PlanItemKind.MONTH_DIVIDER,
                  PlanItemKind.DAY_DIVIDER, PlanItemKind.PHOTO_GROUP)
    assert [item.kind for item in plan.items] == [Y, M, D, P, Y, M, D, P, M, D, P, D, P, D, P]
    assert [p for item in plan.items for p in item.photos] == photos
    days = [item for item in plan.items if item.kind == D]
    assert [(item.year, item.month, item.day) for item in days] == [
        (2024, 12, 31), (2025, 1, 1), (2025, 3, 1), (2025, 3, 2), (2025, 3, 5),
    ]
    assert all(item.page_instance is settings.day_dividers.page for item in days)
    assert all(item.template_id == settings.day_dividers.template_id for item in days)
    groups = [item for item in plan.items if item.kind == P]
    assert [len(item.photos) for item in groups] == [1, 1, 2, 1, 1]
    assert [item.day for item in groups] == [31, 1, 1, 2, 5]


@pytest.mark.parametrize("enabled", [False, True])
def test_undated_and_empty_projects_have_no_day_separator(widget, enabled):
    settings = daily_settings(widget)
    settings.day_dividers = replace(settings.day_dividers, enabled=enabled)
    assert AlbumPlanner().plan([], settings).items == []
    assert AlbumPlanner().plan([photo("undated", None)], settings).items == []


def test_disabled_days_leave_month_groups_intact(widget):
    settings = daily_settings(widget, months=True, years=True)
    settings.day_dividers = replace(settings.day_dividers, enabled=False)
    plan = AlbumPlanner().plan([
        photo("a", datetime(2025, 3, 1)), photo("b", datetime(2025, 3, 5)),
        photo("c", datetime(2025, 4, 1)), photo("undated", None),
    ], settings)
    assert [item.kind for item in plan.items] == [
        PlanItemKind.YEAR_DIVIDER, PlanItemKind.MONTH_DIVIDER, PlanItemKind.PHOTO_GROUP,
        PlanItemKind.MONTH_DIVIDER, PlanItemKind.PHOTO_GROUP,
    ]
    assert [len(item.photos) for item in plan.items if item.photos] == [2, 1]
    assert all(item.day is None for item in plan.items)


@pytest.mark.parametrize("placement", list(DividerPlacement))
@pytest.mark.parametrize("first_day_photos", [1, 2])
def test_day_pagination_reuses_all_placements(widget, placement, first_day_photos):
    settings = daily_settings(widget)
    settings.photo_pages = replace(settings.photo_pages, page=PageInstance(template_id="photo-page-1"))
    settings.day_dividers = replace(settings.day_dividers, placement=placement)
    photos = [photo(str(i), datetime(2025, 3, 1)) for i in range(first_day_photos)]
    photos.append(photo("last", datetime(2025, 3, 5)))
    result = AlbumBuilder(widget._registry).build(photos, settings)
    pages = result.pagination.pages
    days = [p for p in pages if p.kind == PlanItemKind.DAY_DIVIDER]
    assert [(p.year, p.month, p.day) for p in days] == [(2025, 3, 1), (2025, 3, 5)]
    assert all(p.page_instance is settings.day_dividers.page for p in days)
    if placement == DividerPlacement.NATURAL:
        assert days[1].number == first_day_photos + 2
        assert not any(p.is_blank for p in pages)
    else:
        assert all(p.side == PageSide.RIGHT for p in days)
        if placement == DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING:
            assert pages[days[1].number - 2].blank_reason == BlankPageReason.EDITORIAL
    assert [p.day for p in pages if p.photos] == [1] * first_day_photos + [5]
    assert AlbumSummaryBuilder().build(result).divider_pages == 2
    assert [(c.year, c.month) for c in result.pagination.period_end_capacities] == [(2025, 3)]
    # The daily split never creates daily capacity reports.
    natural = PaginationEngine(widget._registry).paginate(result.plan)
    assert not any(p.is_blank for p in natural.pages)


def test_month_capacity_stays_at_month_boundaries(widget):
    settings = daily_settings(widget, months=True, years=True)
    photos = [photo(str(i), date) for i, date in enumerate([
        datetime(2024, 12, 1), datetime(2024, 12, 5),
        datetime(2025, 1, 1), datetime(2025, 1, 2),
    ])]
    result = AlbumBuilder(widget._registry).build(photos, settings)
    assert [(c.year, c.month, c.unused_photo_slots) for c in result.pagination.period_end_capacities] == [
        (2024, 12, 1), (2025, 1, 1),
    ]


@pytest.mark.parametrize("dates,enabled", [
    ([], False), ([None], False), ([datetime(2025, 3, 1)], True),
    ([datetime(2025, 3, 1), datetime(2025, 3, 5)], True),
    ([datetime(2025, 3, 1), datetime(2025, 4, 1)], False),
    ([datetime(2024, 3, 1), datetime(2025, 3, 1)], False),
    ([datetime(2025, 3, 1), None], False),
])
def test_initial_day_choice_uses_whole_project_month(widget, dates, enabled):
    from photoalbum.gui.main_window import MainWindow
    photos = [photo(str(i), date) for i, date in enumerate(dates)]
    MainWindow._update_album_years(SimpleNamespace(_album_settings_widget=widget), photos)
    assert widget.settings().day_dividers.enabled is enabled
    assert widget._day_divider_combo.isEnabled() is enabled
    assert widget._day_divider_settings_button.isEnabled() is enabled
    assert widget._day_placement_combo.isEnabled() is enabled
    assert widget._day_dividers_checkbox.text() == "Séparateurs de jours"


def test_automatic_choice_tracks_photos_but_preserves_user_and_loaded_choices(widget):
    march = [photo("a", datetime(2025, 3, 1))]
    april = photo("b", datetime(2025, 4, 1))
    widget.set_available_photos(march)
    assert widget.settings().day_dividers.enabled
    widget.set_available_photos(march + [april])
    assert not widget.settings().day_dividers.enabled
    widget.set_available_photos(march)
    widget._day_dividers_checkbox.setChecked(False)
    widget.set_available_photos(march)
    assert not widget.settings().day_dividers.enabled
    widget.reset_to_defaults()
    widget.set_available_photos(march)
    saved = widget.settings()
    widget.set_settings(saved)
    widget.set_available_photos(march + [april])
    assert widget.settings().day_dividers.enabled


@pytest.mark.parametrize("placement", list(DividerPlacement))
def test_day_settings_round_trip_and_gui_preserve_instance(widget, placement):
    original = daily_settings(widget)
    original.day_dividers = replace(original.day_dividers, placement=placement, page=PageInstance(
        template_id="day-divider-simple", settings={"day_divider_simple": {"title_font_size": 35}},
    ))
    encoded = album_settings_to_json(original)
    assert json.loads(encoded)["schema_version"] == 2
    restored = album_settings_from_json(encoded)
    assert restored == original
    widget.set_settings(restored)
    assert widget.settings().day_dividers == original.day_dividers
    assert widget.settings().day_dividers.page.instance_id == original.day_dividers.page.instance_id
    data = json.loads(encoded)
    del data["day_dividers"]
    with pytest.raises(KeyError, match="day_dividers"):
        album_settings_from_json(json.dumps(data))


def test_day_role_is_validated_in_settings_and_pack_defaults(widget):
    settings = daily_settings(widget)
    assert widget._registry.get(settings.day_dividers.template_id).supports(TemplateKind.DAY_DIVIDER)
    settings.day_dividers = replace(settings.day_dividers, page=PageInstance(template_id="month-divider-simple"))
    with pytest.raises(ValueError, match="day_divider"):
        AlbumSettingsValidator(widget._registry).validate(settings)
    with pytest.raises(ValueError, match="day_divider"):
        discovery._default_templates({"day_divider": "month-divider-simple"}, widget._registry.list_all())


@pytest.mark.parametrize("language,expected", [("en", "March 1, 2025"), ("fr", "1er mars 2025")])
def test_msb_day_editor_preview_and_pdf_date(widget, tmp_path, language, expected):
    from PySide6.QtGui import QImage
    from pypdf import PdfReader
    from photoalbum.export import PdfExportService
    from photoalbum.templates.msb.day_divider_simple.settings import DayDividerSimpleSettingsWidget
    from photoalbum.templates.msb.day_divider_simple.widget_renderer import day_title

    base = Translator(language)
    translator = translator_for_template("day-divider-simple", base)
    settings = daily_settings(widget)
    instance = settings.day_dividers.page
    editor = DayDividerSimpleSettingsWidget(instance, (), translator=translator)
    try:
        assert not editor._preview.pixmap().isNull()
        image = editor._preview.pixmap().toImage()
        assert len({image.pixel(x, y) for x in range(0, image.width(), 3)
                    for y in range(image.height() // 3, image.height() * 2 // 3, 3)}) > 1
        assert editor.instance() == instance
        editor._size.setValue(36)
        assert editor.instance().settings["day_divider_simple"]["title_font_size"] == 36
        settings.day_dividers = replace(settings.day_dividers, page=editor.instance())
    finally:
        editor.close()
    image = QImage(40, 40, QImage.Format.Format_RGB32)
    image.fill(0x123456)
    path = tmp_path / "photo.png"
    assert image.save(str(path))
    photos = [photo(str(path), datetime(2025, 3, 1))]
    settings.covers = {position: CoverSettings(position=position, template_id="geographic-word-cloud")
                       for position in settings.covers}
    result = AlbumBuilder(widget._registry).build(photos, settings)
    day = next(p for p in result.pagination.pages if p.kind == PlanItemKind.DAY_DIVIDER)
    assert day_title(day, translator) == expected
    output = tmp_path / "days.pdf"
    PdfExportService(base).export(output_path=output, result=result, settings=settings,
                                  photos=photos, page_width_mm=210, page_height_mm=297, dpi=72)
    reader = PdfReader(output)
    assert len(reader.pages) == result.total_page_count
    assert expected in " ".join(" ".join(p.extract_text() for p in reader.pages).split())
