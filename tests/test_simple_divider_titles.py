"""Simple divider titles: pack policy, shared localization and host context."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QLocale, QRect
from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance, PlannedPage, PageSide, PlanItemKind
from photoalbum.album.composition import PageComposition
from photoalbum.gui.template_settings import create_template_settings_editor
from photoalbum.i18n import Translator
from photoalbum.rendering.page_renderer import PageRenderer
from photoalbum.template_engine import register_discovered_template_extensions
from photoalbum.template_engine.api import format_date_parts
from photoalbum.templates.msb.simple_divider_titles import divider_title

Y = PlanItemKind.YEAR_DIVIDER
M = PlanItemKind.MONTH_DIVIDER
D = PlanItemKind.DAY_DIVIDER
PAGE = SimpleNamespace(year=2024, month=3, day=16)


@pytest.mark.parametrize("context,month,day", [
    ((), "Mars 2024", "Samedi 16 mars 2024"),
    ((Y,), "Mars", "Samedi 16 mars"),
    ((M,), "Mars 2024", "Samedi 16"),
    ((Y, M), "Mars", "Samedi 16"),
])
def test_automatic_titles(context, month, day):
    assert divider_title("month", PAGE, {}, Translator("fr"), context) == month
    assert divider_title("day", PAGE, {}, Translator("fr"), context) == day


@pytest.mark.parametrize("context", [(), (Y,), (M,), (Y, M)])
@pytest.mark.parametrize("kind,choice,expected", [
    ("month", "month", "Mars"),
    ("month", "month_year", "Mars 2024"),
    ("day", "weekday_day", "Samedi 16"),
    ("day", "weekday_day_month", "Samedi 16 mars"),
    ("day", "full_date", "Samedi 16 mars 2024"),
])
def test_manual_titles_ignore_context(context, kind, choice, expected):
    settings = {f"{kind}_divider_simple": {"title_format": choice}}
    assert divider_title(kind, PAGE, settings, Translator("fr"), context) == expected


@pytest.mark.parametrize("language,parts,expected", [
    ("fr", {}, "Dimanche 1er mars 2026"),
    ("fr", {"year": False}, "Dimanche 1er mars"),
    ("fr", {"year": False, "month": False}, "Dimanche 1er"),
    ("en", {}, "Sunday, March 1, 2026"),
    ("en", {"year": False}, "Sunday, March 1"),
    ("en", {"year": False, "month": False}, "Sunday 1"),
])
def test_public_date_formatter_handles_language_and_first_day(language, parts, expected):
    previous = QLocale()
    try:
        QLocale.setDefault(QLocale("de_DE"))
        assert format_date_parts(date(2026, 3, 1), language=language, weekday=True, **parts) == expected
    finally:
        QLocale.setDefault(previous)


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    register_discovered_template_extensions()
    return app


@pytest.mark.parametrize("kind,manual,labels", [
    ("month", "month_year", ["Mois et année", "Mois", "Mois et année"]),
    ("day", "full_date", ["Date complète", "Jour, numéro et mois", "Jour et numéro"]),
])
def test_editor_updates_automatic_label_without_changing_saved_choice(app, kind, manual, labels):
    instance = PageInstance(template_id=f"{kind}-divider-simple", settings={
        f"{kind}_divider_simple": {"title_font_size": 35.0}, "other": {"keep": True},
    })
    editor = create_template_settings_editor(instance.template_id, instance, (), translator=Translator("fr"))
    try:
        assert editor.instance() == instance
        assert editor._title_format.currentData() == "auto"
        for context, label in zip(((), (Y,), (M,)), labels):
            editor.set_temporal_context(context)
            assert editor._title_format.itemText(0) == f"Automatique — {label}"
            assert editor.instance() == instance
            assert not editor._preview.pixmap().isNull()
        editor._title_format.setCurrentIndex(editor._title_format.findData(manual))
        saved = editor.instance()
        assert saved.settings[f"{kind}_divider_simple"]["title_format"] == manual
        assert saved.settings[f"{kind}_divider_simple"]["title_font_size"] == 35
        assert saved.settings["other"] == {"keep": True}
        editor.set_temporal_context(())
        assert editor.instance() == saved
        assert editor._title_format.currentData() == manual
        reopened = create_template_settings_editor(saved.template_id, saved, (), translator=Translator("fr"),
                                                    temporal_context=(Y, M))
        assert reopened._title_format.currentData() == manual
        assert reopened.instance() == saved
        reopened.close()
    finally:
        editor.close()


@pytest.mark.parametrize("kind,context,expected", [
    ("month", (), "Mars 2024"), ("month", (Y,), "Mars"),
    ("day", (), "Samedi 16 mars 2024"), ("day", (Y,), "Samedi 16 mars"),
    ("day", (Y, M), "Samedi 16"),
])
def test_renderer_uses_actual_period_pages_and_keeps_typography(app, kind, context, expected):
    page = PlannedPage(3, PageSide.RIGHT, D if kind == "day" else M, f"{kind}-divider-simple",
                       year=2024, month=3, day=16)
    instance = PageInstance(template_id=page.template_id,
                            settings={f"{kind}_divider_simple": {"title_font_size": 35}})
    pages = [PlannedPage(i + 1, PageSide.RIGHT, level, "unused", year=2024, month=3)
             for i, level in enumerate(context)]
    # Dividers for other periods must not influence this page.
    pages.extend([PlannedPage(9, PageSide.RIGHT, Y, "unused", year=2023),
                  PlannedPage(10, PageSide.LEFT, M, "unused", year=2024, month=4)])
    painter = Mock()
    PageRenderer(translator=Translator("fr")).paint_template(
        instance=instance, painter=painter, target_rect=QRect(0, 0, 1200, 1600),
        width=1200, height=1600, page_width_mm=210, page_height_mm=297,
        font_pixel_size=lambda value: int(value), composition=PageComposition(page=page),
        album_pages=pages,
    )
    assert painter.drawText.call_args.args[-1] == expected
    assert painter.setFont.call_args.args[0].bold()
    assert painter.setFont.call_args.args[0].pixelSize() == 35
    from photoalbum.templates.msb.theme import msb_theme_from_pack_settings
    assert painter.setPen.call_args.args[0].getRgb()[:3] == tuple(msb_theme_from_pack_settings({}).color_for_month(3))


def test_album_controls_supply_updated_context_when_reopening_editor(app, monkeypatch):
    from photoalbum.gui.page_instance_dialog import PageInstanceDialog
    from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
    from photoalbum.template_engine import create_template_registry

    host = AlbumSettingsWidget(create_template_registry(), translator=Translator("fr"))
    from datetime import datetime
    from pathlib import Path
    from photoalbum.models import Photo
    host.set_photo_provider(lambda: [Photo(path=Path("a.jpg"), filename="a.jpg",
                                          capture_datetime=datetime(2024, 3, 16))])
    host._day_dividers_checkbox.setChecked(True)
    host.set_available_years({2024})
    labels = []
    def inspect_dialog(dialog):
        labels.append(dialog._editor._title_format.itemText(0))
        return 0
    monkeypatch.setattr(PageInstanceDialog, "exec", inspect_dialog)
    try:
        for years, months in [(True, True), (True, False), (False, False)]:
            host._year_dividers_checkbox.setChecked(years)
            host._month_dividers_checkbox.setChecked(months)
            host._configure_divider_instance("day")
        assert labels == ["Automatique — Jour et numéro", "Automatique — Jour, numéro et mois",
                          "Automatique — Date complète"]
    finally:
        host.close()


@pytest.mark.parametrize("kind", ["day", "month"])
@pytest.mark.parametrize("dates", [[], [None], ["2024-03-16"], ["2024-03-16", "2026-09-02"]])
@pytest.mark.parametrize("years,months", [(False, False), (True, False), (False, True), (True, True)])
def test_dialog_label_preview_and_final_render_share_materialized_context(
    app, monkeypatch, kind, dates, years, months,
):
    from datetime import datetime
    from pathlib import Path
    from photoalbum.models import Photo
    from photoalbum.album import AlbumBuilder
    from photoalbum.gui.page_instance_dialog import PageInstanceDialog
    from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
    from photoalbum.template_engine import create_template_registry, template_extension_registry
    from photoalbum.rendering.temporal_context import materialized_periods
    from photoalbum.templates.msb.simple_divider_titles import automatic_format

    registry = create_template_registry()
    host = AlbumSettingsWidget(registry, translator=Translator("fr"))
    photos = [Photo(path=Path(f"{i}.jpg"), filename=f"{i}.jpg",
                    capture_datetime=datetime.fromisoformat(value) if value else None)
              for i, value in enumerate(dates)]
    host.set_photo_provider(lambda: photos)
    # Deliberately leave the UI's available-years hint stale. Only the build counts.
    host._year_dividers_checkbox.setChecked(years)
    host._month_dividers_checkbox.setChecked(months)
    host._day_dividers_checkbox.setChecked(True)
    combo = getattr(host, f"_{kind}_divider_combo")
    combo.setCurrentIndex(combo.findData(f"{kind}-divider-simple"))
    pages = AlbumBuilder(registry).build(photos, host.settings()).pagination.pages
    target = next((p for p in pages if p.kind == (D if kind == "day" else M)), None)
    expected_context = materialized_periods(target, pages)
    renderer = template_extension_registry.get(f"{kind}-divider-simple").widget_renderer
    render_calls = []
    original_paint = renderer.paint
    def record_paint(**kwargs):
        render_calls.append(kwargs)
        original_paint(**kwargs)
    monkeypatch.setattr(renderer, "paint", record_paint)

    def inspect_dialog(dialog):
        editor = dialog._editor
        preview = render_calls[-1]
        assert editor._temporal_context == preview["temporal_context"] == expected_context
        format_label = editor._translator.tr(f"divider_title.{automatic_format(kind, expected_context)}")
        assert editor._title_format.itemText(0) == f"Automatique — {format_label}"
        if target is not None:
            preview_page = preview["composition"].page
            assert (preview_page.year, preview_page.month) == (target.year, target.month)
            if kind == "day":
                assert preview_page.day == target.day
            painter = Mock()
            PageRenderer(translator=Translator("fr")).paint_template(
                instance=editor.instance(), painter=painter, target_rect=QRect(0, 0, 1200, 1600),
                width=1200, height=1600, page_width_mm=210, page_height_mm=297,
                font_pixel_size=int, composition=PageComposition(page=target), album_pages=pages,
            )
            assert render_calls[-1]["temporal_context"] == expected_context
            assert painter.drawText.call_args.args[-1] == divider_title(
                kind, preview_page, editor.instance().settings, editor._translator, expected_context,
            )
        else:
            assert not expected_context
        return 0

    monkeypatch.setattr(PageInstanceDialog, "exec", inspect_dialog)
    try:
        host._configure_divider_instance(kind)
    finally:
        host.close()


@pytest.mark.parametrize("language,expected", [
    ("en", ["", "2026", "March", "March 2026", "1", "1 2026", "March 1", "March 1, 2026",
            "Sunday", "Sunday 2026", "Sunday March", "Sunday March 2026", "Sunday 1",
            "Sunday 1 2026", "Sunday, March 1", "Sunday, March 1, 2026"]),
    ("fr", ["", "2026", "Mars", "Mars 2026", "1er", "1er 2026", "1er mars", "1er mars 2026",
            "Dimanche", "Dimanche 2026", "Dimanche mars", "Dimanche mars 2026", "Dimanche 1er",
            "Dimanche 1er 2026", "Dimanche 1er mars", "Dimanche 1er mars 2026"]),
])
def test_date_formatter_all_component_subsets(language, expected):
    from itertools import product
    choices = list(product((False, True), repeat=4))
    actual = [format_date_parts(date(2026, 3, 1), language=language,
                               weekday=w, day=d, month=m, year=y) for w, d, m, y in choices]
    assert actual == expected
    # A regional tag follows the documented language-level convention.
    assert [format_date_parts(date(2026, 3, 1), language=language + "-CA",
                              weekday=w, day=d, month=m, year=y) for w, d, m, y in choices] == expected


def test_date_formatter_regular_day_and_leap_day():
    assert format_date_parts(date(2024, 2, 29), language="fr", weekday=True) == "Jeudi 29 février 2024"
    assert format_date_parts(date(2024, 2, 29), language="en", weekday=True) == "Thursday, February 29, 2024"
    with pytest.raises(ValueError, match="Unsupported date language"):
        format_date_parts(date(2024, 2, 29), language="unknown")
