from photoalbum.album.settings import AlbumStructureSettings, DividerSettings
from photoalbum.template_engine.defaults import default_template_choices
from photoalbum.template_engine import create_template_registry

def _settings(enabled=True):
    value = object.__new__(AlbumStructureSettings)
    value.year_dividers = DividerSettings(
        enabled=enabled,
        template_id="calendar-index",
    )
    return value

def test_default_year_divider_is_calendar_index():
    assert default_template_choices(create_template_registry()).year_divider == "calendar-index"

def test_year_divider_is_available_for_single_year():
    settings = _settings()
    assert settings.year_dividers_available({2024})
    assert settings.should_use_year_dividers({2024})

def test_year_divider_is_unavailable_without_dated_year():
    settings = _settings()
    assert not settings.year_dividers_available(set())
    assert not settings.should_use_year_dividers(set())
