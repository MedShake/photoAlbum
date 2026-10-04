from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox

from photoalbum.geocoding import order_location_components
from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.models import (
    LocationComponent,
    LocationSource,
    MetadataCandidates,
    Photo,
)
from photoalbum.sources import PhotoMetadataPolicy, resolve_photo_metadata


@pytest.fixture(autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _policy(location: str) -> PhotoMetadataPolicy:
    return PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference=location,
        nominatim_enabled=True,
    )


def _photo(name: str = "photo.jpg") -> Photo:
    return Photo(
        path=Path("/tmp") / name,
        filename=name,
        capture_datetime=datetime(2025, 7, 14),
        exif_capture_datetime=datetime(2025, 7, 14),
        exif_latitude=48.8566,
        exif_longitude=2.3522,
        metadata_candidates=MetadataCandidates(
            location={
                "provider": {
                    "components": [
                        {"key": "country", "value": "France"},
                        {"key": "city", "value": "Paris"},
                        {"key": "road", "value": "Rue de Rivoli"},
                        {"key": "house_number", "value": "99"},
                        {"key": "tourism", "value": "Musée du Louvre"},
                    ]
                },
                "geocoding": {
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "raw": {
                        "address": {
                            "country": "France",
                            "postcode": "44000",
                            "city": "Nantes",
                            "suburb": "Centre-ville",
                            "road": "Rue de Strasbourg",
                            "amenity": "Musée d'arts",
                        }
                    },
                },
            }
        ),
    )


def _materialize(widget: PhotoPlacesWidget, photo: Photo):
    app = QApplication.instance() or QApplication([])
    widget.set_photos([photo])
    year = widget._tree.topLevelItem(0)
    year.setExpanded(True)
    month = year.child(0)
    month.setExpanded(True)
    for _ in range(5):
        app.processEvents()
    return widget._location_mode_boxes[str(photo.path)]


def _checkbox_values(widget: PhotoPlacesWidget, photo: Photo) -> list[str]:
    automatic = widget._location_mode_widgets[str(photo.path)][0]
    return [box.text() for box in automatic.findChildren(QCheckBox)]


@pytest.mark.parametrize(
    ("preference", "expected", "source"),
    [
        ("source", "Synology Photos", LocationSource.SOURCE),
        ("geocoding", "Nominatim", LocationSource.GEOCODING),
    ],
)
def test_project_policy_selects_initial_photo_source(
    preference: str,
    expected: str,
    source: LocationSource,
):
    photo = resolve_photo_metadata(_photo(preference + ".jpg"), _policy(preference))
    assert photo.location_source == source
    widget = PhotoPlacesWidget()
    widget.set_provider_context("Synology Photos")

    combo = _materialize(widget, photo)

    assert combo.currentText() == expected
    widget.close()


def test_manual_photo_override_is_preserved():
    photo = _photo("manual.jpg")
    photo.location_source = LocationSource.MANUAL
    photo.location_text = "Mon endroit"
    photo.location_selection_edited = True
    photo.manual_location_data = {
        "address": "Mon endroit",
        "components": [],
        "raw": {"address": {}},
        "photo_places": {
            "origin": "manual",
            "selections": {"manual": []},
            "texts": {"manual": "Mon endroit"},
        },
    }
    widget = PhotoPlacesWidget()

    combo = _materialize(widget, photo)

    assert combo.currentData() == "manual"
    assert widget._location_mode_widgets[str(photo.path)][2].text() == "Mon endroit"
    widget.close()


def test_persisted_components_are_checked_for_the_effective_source():
    photo = resolve_photo_metadata(_photo("selection.jpg"), _policy("source"))
    photo.manual_location_data = {
        "photo_places": {
            "origin": "provider",
            "selections": {
                "provider": [{"key": "city", "value": "Paris"}],
            },
            "texts": {"provider": "Paris"},
        }
    }
    widget = PhotoPlacesWidget()
    _materialize(widget, photo)
    automatic = widget._location_mode_widgets[str(photo.path)][0]

    checked = [
        box.text()
        for box in automatic.findChildren(QCheckBox)
        if box.isChecked()
    ]

    assert checked == ["Paris"]
    widget.close()


def test_dropdown_change_is_local_and_does_not_change_project_policy():
    policy = _policy("source")
    photo = resolve_photo_metadata(_photo("local-override.jpg"), policy)
    saves = []
    widget = PhotoPlacesWidget(
        save_location_override=lambda *args: saves.append(args)
    )
    widget.set_provider_context("Synology Photos")
    combo = _materialize(widget, photo)

    combo.setCurrentIndex(combo.findData("geocoding"))

    assert policy.location_preference == "source"
    assert photo.manual_location_data["photo_places"]["origin"] == "geocoding"
    assert saves[-1][3]["photo_places"]["origin"] == "geocoding"
    resolved = resolve_photo_metadata(photo, policy)
    assert resolved.location_source == LocationSource.GEOCODING
    assert resolved.raw_location_data["address"]["city"] == "Nantes"
    widget.close()


def test_components_are_precise_to_general_and_only_active_source_is_visible():
    photo = resolve_photo_metadata(_photo("order.jpg"), _policy("source"))
    widget = PhotoPlacesWidget()
    widget.set_provider_context("Synology Photos")
    combo = _materialize(widget, photo)

    assert [combo.itemText(index) for index in range(combo.count())] == [
        "Synology Photos",
        "Nominatim",
        "Custom",
        "None",
    ]
    assert _checkbox_values(widget, photo) == [
        "Musée du Louvre",
        "99",
        "Rue de Rivoli",
        "Paris",
        "France",
    ]
    assert "Nantes" not in _checkbox_values(widget, photo)

    combo.setCurrentIndex(combo.findData("geocoding"))
    assert _checkbox_values(widget, photo) == [
        "Musée d'arts",
        "Rue de Strasbourg",
        "Centre-ville",
        "Nantes",
        "44000",
        "France",
    ]
    assert "Paris" not in _checkbox_values(widget, photo)
    widget.close()


def test_checkbox_composition_is_kept_per_source():
    photo = resolve_photo_metadata(_photo("per-source.jpg"), _policy("source"))
    widget = PhotoPlacesWidget(save_location_override=lambda *_args: None)
    combo = _materialize(widget, photo)
    automatic = widget._location_mode_widgets[str(photo.path)][0]
    paris = next(
        box
        for box in automatic.findChildren(QCheckBox)
        if box.text() == "Paris"
    )
    paris.setChecked(False)

    combo.setCurrentIndex(combo.findData("geocoding"))
    combo.setCurrentIndex(combo.findData("provider"))

    automatic = widget._location_mode_widgets[str(photo.path)][0]
    checked = {
        box.text()
        for box in automatic.findChildren(QCheckBox)
        if box.isChecked()
    }
    assert "Paris" not in checked
    assert photo.manual_location_data["photo_places"]["origin"] == "provider"
    widget.close()


def test_provider_label_is_provider_neutral_for_immich():
    photo = resolve_photo_metadata(_photo("immich.jpg"), _policy("source"))
    widget = PhotoPlacesWidget()
    widget.set_provider_context("Immich")

    combo = _materialize(widget, photo)

    assert combo.currentText() == "Immich"
    assert combo.itemData(0) == "provider"
    assert _checkbox_values(widget, photo)[0] == "Musée du Louvre"
    widget.close()


def test_unknown_component_keys_stay_stable_after_known_categories():
    values = tuple(
        LocationComponent(key=key, value=key)
        for key in ("mystery_b", "country", "road", "mystery_a", "tourism")
    )

    ordered = order_location_components(values)

    assert [component.key for component in ordered] == [
        "tourism",
        "road",
        "country",
        "mystery_b",
        "mystery_a",
    ]
