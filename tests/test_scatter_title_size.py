from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.rendering.fonts import (
    available_photo_album_fonts,
    resolve_font_family,
)
from photoalbum.templates.msb.year_photo_scatter.settings import (
    YearPhotoScatterSettingsWidget,
)
from photoalbum.templates.msb.year_photo_scatter.title_style import (
    title_font_family,
    title_font_size,
)


# title_font_family() ultimately queries QFontDatabase.
_app = QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "title,size",
    [
        ("2025", 72),
        ("2024–2025", 52),
        ("Juin 2025", 44),
    ],
)
def test_title_size_defaults_and_override(title, size):
    assert title_font_size({}, title) == size
    assert (
        title_font_size(
            {"scatter": {"title_font_size": 36.5}},
            title,
        )
        == 36.5
    )


@pytest.mark.parametrize(
    "value",
    [None, "invalid", float("nan"), -1, 301],
)
def test_invalid_title_size_uses_default(value):
    assert (
        title_font_size(
            {"scatter": {"title_font_size": value}},
            "2025",
        )
        == 72
    )


def test_title_font_family_defaults_to_application_font():
    assert title_font_family({}) == resolve_font_family(None)


def test_title_font_family_accepts_available_font():
    fonts = available_photo_album_fonts()
    assert fonts

    family = fonts[-1]

    assert (
        title_font_family(
            {"scatter": {"title_font_family": family}}
        )
        == family
    )


def test_title_font_family_rejects_unknown_font():
    assert (
        title_font_family(
            {
                "scatter": {
                    "title_font_family":
                        "Definitely Not A Photo Album Font"
                }
            }
        )
        == resolve_font_family(None)
    )


def test_title_editor_preserves_and_reloads_settings(monkeypatch):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    photos = [
        Photo(
            path=Path("photo.jpg"),
            filename="photo.jpg",
            capture_datetime=datetime(2025, month, 1),
        )
        for month in (1, 6)
    ]

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        photos,
        translator=Translator("fr"),
    )

    assert editor._title_font_size_spin.value() == 72
    assert (
        editor._title_font_combo.currentData()
        == resolve_font_family(None)
    )

    fonts = available_photo_album_fonts()
    assert fonts

    selected_family = next(
        (
            family
            for family in fonts
            if family != editor._title_font_combo.currentData()
        ),
        fonts[0],
    )

    changes = []
    editor.instance_changed.connect(
        lambda: changes.append(True)
    )

    font_index = editor._title_font_combo.findData(
        selected_family
    )
    assert font_index >= 0

    editor._title_font_combo.setCurrentIndex(
        font_index
    )
    editor._title_font_size_spin.setValue(38.5)

    settings = editor.instance().settings["scatter"]

    assert settings["title_font_family"] == selected_family
    assert settings["title_font_size"] == 38.5
    assert len(changes) == 2

    # Generating another scatter proposal must preserve
    # the title style settings.
    editor._new()

    settings = editor.instance().settings["scatter"]

    assert settings["title_font_family"] == selected_family
    assert settings["title_font_size"] == 38.5

    reopened = YearPhotoScatterSettingsWidget(
        editor.instance(),
        photos,
        translator=Translator("fr"),
    )

    assert (
        reopened._title_font_combo.currentData()
        == selected_family
    )
    assert reopened._title_font_size_spin.value() == 38.5

    editor.close()
    reopened.close()


def test_title_visibility_and_position_defaults(monkeypatch):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        [],
        translator=Translator("fr"),
    )

    assert editor._title_visible_check.isChecked()
    assert (
        editor._title_position_combo.currentData()
        == "center"
    )
    assert editor._title_position_combo.isEnabled()
    assert editor._title_color_button.isEnabled()
    assert editor._title_font_combo.isEnabled()
    assert editor._title_font_size_spin.isEnabled()

    editor.close()


def test_title_defaults_to_automatic_mode(
    monkeypatch,
):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        [],
        translator=Translator("fr"),
    )

    assert editor._title_mode == "automatic"
    assert editor._title_text == ""
    assert (
        editor._title_mode_combo.currentData()
        == "automatic"
    )
    assert not editor._title_text_edit.isEnabled()
    assert editor._title_text_label.isHidden()
    assert editor._title_text_edit.isHidden()

    editor.close()


def test_custom_title_markdown_is_persisted(
    monkeypatch,
):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        [],
        translator=Translator("fr"),
    )

    custom_index = (
        editor._title_mode_combo.findData(
            "custom"
        )
    )
    assert custom_index >= 0

    editor._title_mode_combo.setCurrentIndex(
        custom_index
    )
    editor._title_text_edit.setPlainText(
        "**Voyage** *en famille*"
    )

    scatter = editor._instance.settings["scatter"]

    assert scatter["title_mode"] == "custom"
    assert (
        scatter["title_text"]
        == "**Voyage** *en famille*"
    )
    assert editor._title_text_edit.isEnabled()
    assert not editor._title_text_label.isHidden()
    assert not editor._title_text_edit.isHidden()

    editor.close()


def test_custom_title_is_retained_when_switching_modes(
    monkeypatch,
):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(
            template_id="year-photo-scatter",
            settings={
                "scatter": {
                    "title_mode": "custom",
                    "title_text": "**Souvenir**",
                }
            },
        ),
        [],
        translator=Translator("fr"),
    )

    automatic_index = (
        editor._title_mode_combo.findData(
            "automatic"
        )
    )
    assert automatic_index >= 0

    editor._title_mode_combo.setCurrentIndex(
        automatic_index
    )

    scatter = editor._instance.settings["scatter"]

    assert scatter["title_mode"] == "automatic"
    assert scatter["title_text"] == "**Souvenir**"
    assert not editor._title_text_edit.isEnabled()
    assert editor._title_text_label.isHidden()
    assert editor._title_text_edit.isHidden()

    custom_index = (
        editor._title_mode_combo.findData(
            "custom"
        )
    )
    assert custom_index >= 0

    editor._title_mode_combo.setCurrentIndex(
        custom_index
    )

    assert (
        editor._title_text_edit.toPlainText()
        == "**Souvenir**"
    )
    assert editor._title_text_edit.isEnabled()
    assert not editor._title_text_label.isHidden()
    assert not editor._title_text_edit.isHidden()

    editor.close()


def test_title_position_combo_exposes_seven_ordered_positions(
    monkeypatch,
):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        [],
        translator=Translator("fr"),
    )

    assert [
        editor._title_position_combo.itemData(index)
        for index in range(
            editor._title_position_combo.count()
        )
    ] == [
        "very_high",
        "high",
        "upper_middle",
        "center",
        "lower_middle",
        "low",
        "very_low",
    ]

    assert [
        editor._title_position_combo.itemText(index)
        for index in range(
            editor._title_position_combo.count()
        )
    ] == [
        "Très haute",
        "Haute",
        "Mi-haute",
        "Centrée",
        "Mi-basse",
        "Basse",
        "Très basse",
    ]

    editor.close()


def test_title_visibility_preserves_style_and_position(monkeypatch):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(
            template_id="year-photo-scatter",
            settings={
                "scatter": {
                    "title_color": "#123456",
                    "title_font_size": 38.5,
                    "title_position": "very_low",
                }
            },
        ),
        [],
        translator=Translator("fr"),
    )

    editor._title_visible_check.setChecked(False)

    settings = editor.instance().settings["scatter"]

    assert settings["title_visible"] is False
    assert settings["title_position"] == "very_low"
    assert settings["title_color"] == "#123456"
    assert settings["title_font_size"] == 38.5

    assert not editor._title_position_combo.isEnabled()
    assert not editor._title_color_button.isEnabled()
    assert not editor._title_font_combo.isEnabled()
    assert not editor._title_font_size_spin.isEnabled()

    editor._title_visible_check.setChecked(True)

    settings = editor.instance().settings["scatter"]
    assert settings["title_visible"] is True
    assert settings["title_position"] == "very_low"
    assert settings["title_color"] == "#123456"
    assert settings["title_font_size"] == 38.5

    editor.close()


def test_title_position_is_persisted_and_reloaded(monkeypatch):
    monkeypatch.setattr(
        YearPhotoScatterSettingsWidget,
        "_request_preview",
        lambda self: None,
    )

    editor = YearPhotoScatterSettingsWidget(
        PageInstance(template_id="year-photo-scatter"),
        [],
        translator=Translator("fr"),
    )

    index = editor._title_position_combo.findData(
        "very_high"
    )
    assert index >= 0

    editor._title_position_combo.setCurrentIndex(
        index
    )

    assert (
        editor.instance().settings["scatter"][
            "title_position"
        ]
        == "very_high"
    )

    reopened = YearPhotoScatterSettingsWidget(
        editor.instance(),
        [],
        translator=Translator("fr"),
    )

    assert (
        reopened._title_position_combo.currentData()
        == "very_high"
    )

    editor.close()
    reopened.close()
