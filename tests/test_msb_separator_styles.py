from PySide6.QtWidgets import QApplication
from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.rendering.fonts import available_photo_album_fonts
from photoalbum.templates.msb.divider_style import divider_font_size
from photoalbum.templates.msb.calendar_index.settings import CalendarIndexSettingsWidget
from photoalbum.templates.msb.month_divider_simple.settings import MonthDividerSimpleSettingsWidget
from photoalbum.templates.msb.photo_page.settings import PhotoPageSettingsWidget
from photoalbum.templates.msb.year_divider_classic.settings import YearDividerClassicSettingsWidget

_app = QApplication.instance() or QApplication([])

def test_simple_divider_size_default_and_override():
    assert divider_font_size({}, "year_divider") == 72
    assert divider_font_size({"year_divider":{"title_font_size":48.5}}, "year_divider") == 48.5

def test_calendar_index_editor_does_not_mutate_settings_on_init():
    instance = PageInstance(
        template_id="calendar-index"
    )

    editor = CalendarIndexSettingsWidget(
        instance,
        (),
        translator=Translator("fr"),
    )

    assert editor.instance().settings == instance.settings

    editor.close()


def test_photo_page_editors_do_not_mutate_settings_on_init():
    for template_id in (
        "photo-page-1",
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
    ):
        instance = PageInstance(
            template_id=template_id
        )

        editor = PhotoPageSettingsWidget(
            instance,
            (),
            translator=Translator("fr"),
        )

        assert editor.instance().settings == instance.settings

        editor.close()


def test_month_simple_editor_preserves_default_font_size_on_init():
    instance = PageInstance(
        template_id="month-divider-simple"
    )

    editor = MonthDividerSimpleSettingsWidget(
        instance,
        (),
        translator=Translator("fr"),
    )

    assert editor._size.value() == 72.0
    assert editor.instance().settings == instance.settings

    editor.close()


def test_year_classic_editor_preserves_default_font_size_on_init():
    instance = PageInstance(
        template_id="year-divider-classic"
    )

    editor = YearDividerClassicSettingsWidget(
        instance,
        (),
        translator=Translator("fr"),
    )

    assert editor._size.value() == 72.0
    assert editor.instance().settings == instance.settings

    editor.close()


def test_month_simple_editor_persists_font_settings():
    editor=MonthDividerSimpleSettingsWidget(PageInstance(template_id="month-divider-simple"),(),translator=Translator("fr"))
    fonts=available_photo_album_fonts(); assert fonts
    editor._size.setValue(54.0)
    assert editor.instance().settings["month_divider_simple"]["title_font_size"] == 54.0
    editor.close()
