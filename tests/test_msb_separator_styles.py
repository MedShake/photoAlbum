from PySide6.QtWidgets import QApplication
from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.rendering.fonts import available_photo_album_fonts
from photoalbum.templates.msb.divider_style import divider_font_size
from photoalbum.templates.msb.calendar_index.settings import CalendarIndexSettingsWidget
from photoalbum.templates.msb.month_divider_simple.settings import MonthDividerSimpleSettingsWidget

_app = QApplication.instance() or QApplication([])

def test_simple_divider_size_default_and_override():
    assert divider_font_size({}, "year_divider") == 72
    assert divider_font_size({"year_divider":{"title_font_size":48.5}}, "year_divider") == 48.5

def test_month_simple_editor_persists_font_settings():
    editor=MonthDividerSimpleSettingsWidget(PageInstance(template_id="month-divider-simple"),(),translator=Translator("fr"))
    fonts=available_photo_album_fonts(); assert fonts
    editor._size.setValue(54.0)
    assert editor.instance().settings["month_divider_simple"]["title_font_size"] == 54.0
    editor.close()
