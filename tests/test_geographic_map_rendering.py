"""Geometric and end-to-end regressions for the Geographic Map pipeline."""
from datetime import datetime
from math import hypot, isfinite

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.template_engine import translator_for_template, register_discovered_template_extensions
from photoalbum.templates.msb.geographic_map import painter as map_painter
from photoalbum.templates.msb.geographic_map.composition import compose_geographic_map
from photoalbum.templates.msb.geographic_map.geography import (
    GeographicBounds, bounds_for_rings, containing_component, continuous_ring,
    country_components, load_countries, world_offsets,
)
from photoalbum.templates.msb.geographic_map.preview import GeographicMapPreviewBackend
from photoalbum.templates.msb.geographic_map.widget_renderer import GeographicMapWidgetRenderer
from photoalbum.templates.msb.theme import MsbTheme, pack_settings_with_msb_theme

SCENARIOS = {
    'france': [(-1.5536, 47.2184)],
    'europe': [(-1.5536, 47.2184), (13.4, 52.5), (25.7294, 66.5039)],
    'china': [(116.4074, 39.9042), (121.4737, 31.2304)],
    'atlantic': [(-74.006, 40.7128), (-1.5536, 47.2184), (25.7294, 66.5039)],
    'fiji': [(179.5, -17.7), (-179.5, -17.4), (178.8, -18.1)],
    'ocean': [(0, -30)],
    'identical': [(0, -30), (0, -30)],
    'empty': [],
}


def photos_for(points):
    photos = []
    for index, (longitude, latitude) in enumerate(points):
        photo = Photo(path=f'/tmp/map-{index}.jpg', filename=f'map-{index}.jpg')
        photo.longitude = longitude
        photo.latitude = latitude
        photo.capture_datetime = datetime(2026, index % 12 + 1, 1)
        photos.append(photo)
    return photos


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
def test_real_russia_small_edges_stay_small_in_painted_path(app, monkeypatch, projection):
    """Exercise the actual polygon paint path, not only the unwrapping helper."""
    composition = compose_geographic_map(photos_for(SCENARIOS['atlantic']))
    source = next(c for c in load_countries() if c.name == 'Russia').rings[18]
    ring = continuous_ring(source)
    monkeypatch.setattr(map_painter, '_visible_rings', lambda bounds: (ring,))
    paths = []

    class Recorder(QPainter):
        def drawPath(self, path):
            paths.append(path)
            super().drawPath(path)

    image = QImage(1200, 800, QImage.Format.Format_ARGB32)
    painter = Recorder(image)
    try:
        map_painter.paint_geographic_map(painter, QRectF(0, 0, 1200, 800), composition, projection=projection)
    finally:
        painter.end()
    path = paths[0]
    for index, (previous, current) in enumerate(zip(ring, ring[1:])):
        if hypot(current[0] - previous[0], current[1] - previous[1]) < 1:
            a, b = path.elementAt(index), path.elementAt(index + 1)
            assert hypot(b.x - a.x, b.y - a.y) < 1200 * .05


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_scenario_markers_and_uniform_scale(scenario, projection):
    composition = compose_geographic_map(photos_for(SCENARIOS[scenario]))
    bounds = composition.bounds
    assert 0 < bounds.longitude_span <= 360
    rect = map_painter._map_rect(bounds, QRectF(0, 0, 1200, 800), projection)
    pb = map_painter._projected_bounds(bounds, projection)
    assert rect.width() / (pb[2] - pb[0]) == pytest.approx(rect.height() / (pb[3] - pb[1]))
    for marker in composition.markers:
        point = map_painter._project(marker.longitude, marker.latitude, bounds, rect, projection, pb)
        assert isfinite(point.x()) and isfinite(point.y())
        assert rect.adjusted(-.001, -.001, .001, .001).contains(point)
        assert 0 <= marker.x <= 1 and 0 <= marker.y <= 1


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
def test_dateline_polygon_and_markers_share_world_copy(projection):
    bounds = GeographicBounds(178, -20, 182, -10)
    ring = ((179, -18), (-179, -18), (-179, -12), (179, -12), (179, -18))
    placed = continuous_ring(ring)
    rect = map_painter._map_rect(bounds, QRectF(0, 0, 900, 600), projection)
    for canonical, local in zip(ring, placed):
        marker = map_painter._project(*canonical, bounds, rect, projection)
        vertex = map_painter._project_continuous(*local, bounds, rect, projection)
        assert vertex.x() == pytest.approx(marker.x())
        assert vertex.y() == pytest.approx(marker.y())
    assert placed[0] == placed[-1]


def test_component_extent_does_not_cut_through_polygon_interior():
    # Sparse vertices must not make the occupied [-100, 100] interval look
    # like its 160-degree complement around the dateline.
    ring = ((-100, 0), (0, 0), (100, 0), (100, 10), (0, 10), (-100, 10), (-100, 0))
    bounds = bounds_for_rings([ring])
    assert bounds.minimum_longitude == -100
    assert bounds.maximum_longitude == 100


def test_world_copies_are_selected_for_whole_components():
    extent = GeographicBounds(170, -20, 190, 0)
    assert list(world_offsets(extent, GeographicBounds(-180, -90, 180, 90))) == [-360, 0]
    assert list(world_offsets(extent, GeographicBounds(890, -20, 910, 0))) == [720]
    assert list(world_offsets(GeographicBounds(-5, -20, 5, 0), extent)) == []


def test_clipping_closes_on_world_seam():
    ring = ((170, -20), (190, -20), (190, -10), (170, -10), (170, -20))
    clipped = map_painter._clip_world(ring, -180, 180)
    assert set(clipped) == {(170, -20), (180, -20), (180, -10), (170, -10)}
    assert continuous_ring(ring)[0] == continuous_ring(ring)[-1]


def test_dateline_component_containment_uses_same_geometry():
    from photoalbum.templates.msb.geographic_map.geography import Country
    ring = ((179, -20), (-179, -20), (-179, -10), (179, -10), (179, -20))
    country = Country('Example', 'EX', 'EXP', (ring,))
    assert containing_component(-179.5, -15, (country,)) is not None
    assert containing_component(179.5, -15, (country,)) is not None
    assert containing_component(0, -15, (country,)) is None


def test_invalid_and_duplicate_photos_are_consistent():
    photos = photos_for([(float('nan'), 0), (0, float('inf')), (181, 0), (0, 91), (None, 0), ('bad', 0), (0, -30)])
    photos.append(photos[-1])
    composition = compose_geographic_map(photos)
    assert len(composition.markers) == 1
    backend = GeographicMapPreviewBackend()
    assert len(backend.effective_photos(PageInstance(template_id='geographic-map'), photos)) == 1


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
@pytest.mark.parametrize('mode', ['month', 'single', 'empty'])
def test_preview_worker_matches_final_render(app, projection, mode):
    register_discovered_template_extensions()
    translator = translator_for_template('geographic-map', Translator('fr'))
    instance = PageInstance(template_id='geographic-map', settings={'geographic_map': {
        'projection': projection, 'point_color_mode': mode if mode != 'empty' else 'month',
        'point_color': '#008800', 'point_size': .011, 'point_opacity': .4,
        'land_color': '#faf4d0', 'border_color': '#918273', 'show_month_legend': True,
        'year': 2026,
    }})
    theme = MsbTheme()
    theme.month_colors[1] = (255, 0, 255)
    pack_settings = pack_settings_with_msb_theme({}, theme)
    photos = photos_for(SCENARIOS['fiji']) if mode != 'empty' else []
    if photos:
        photos.append(photos[0])
    backend = GeographicMapPreviewBackend()
    job = backend.create_job(request_id='test', instance=instance, photos=photos,
        width=600, height=400, page_width_mm=210, page_height_mm=140,
        translator=translator, template_pack_settings=pack_settings)
    results, errors = [], []
    job.worker.signals.finished.connect(lambda key, data: results.append(data))
    job.worker.signals.failed.connect(lambda key, message: errors.append(message))
    job.worker.run()
    assert not errors
    assert len(results) == 1
    preview = QImage.fromData(results[0]).convertToFormat(QImage.Format.Format_ARGB32)
    final = QImage(600, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(final)
    try:
        GeographicMapWidgetRenderer().paint(painter=painter, instance=instance,
            photos=photos, target_rect=QRectF(0, 0, 600, 400), width=600, height=400,
            translator=translator, render_service=None, set_waiting_key=None,
            font_pixel_size=lambda size: size, template_pack_settings=pack_settings)
    finally:
        painter.end()
    assert preview == final


def test_preview_defers_composition_and_snapshots_photos(app, monkeypatch):
    from photoalbum.templates.msb.geographic_map import render_worker
    def forbidden(*args, **kwargs):
        raise AssertionError('Composition must only run inside worker.run')
    monkeypatch.setattr(render_worker, 'compose_geographic_map', forbidden)
    photos = photos_for(SCENARIOS['france'])
    backend = GeographicMapPreviewBackend()
    job = backend.create_job(request_id='test', instance=PageInstance(template_id='geographic-map'),
        photos=photos, width=600, height=400, page_width_mm=210, page_height_mm=140,
        translator=Translator('en'))
    photos[0].longitude = 100
    assert job.worker.photos[0].longitude == -1.5536


def test_preview_signatures_track_projection_gps_and_theme():
    backend = GeographicMapPreviewBackend()
    instance = PageInstance(template_id='geographic-map', settings={'geographic_map': {}})
    original = backend.render_settings_signature(instance)
    instance.settings['geographic_map']['projection'] = 'robinson'
    assert backend.render_settings_signature(instance) != original
    theme = MsbTheme()
    theme.month_colors[1] = (1, 2, 3)
    assert backend.render_settings_signature(instance, template_pack_settings=pack_settings_with_msb_theme({}, theme)) != backend.render_settings_signature(instance)
    photo = photos_for(SCENARIOS['france'])[0]
    original = backend.photo_signature(photo)
    photo.longitude = 10
    assert backend.photo_signature(photo) != original


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
def test_projection_geometry_is_invariant_under_world_rotation(projection):
    # Moving the central meridian must rotate the map, not shear Fiji by
    # projecting its absolute longitude relative to Greenwich.
    equatorial = GeographicBounds(-5, -30, 5, 20)
    pacific = GeographicBounds(175, -30, 185, 20)
    target = QRectF(0, 0, 900, 600)
    for longitude, latitude in [(-3, -20), (0, 0), (4, 15)]:
        a = map_painter._project(longitude, latitude, equatorial,
            map_painter._map_rect(equatorial, target, projection), projection)
        b = map_painter._project(longitude + 180, latitude, pacific,
            map_painter._map_rect(pacific, target, projection), projection)
        assert a.x() == pytest.approx(b.x())
        assert a.y() == pytest.approx(b.y())


def test_all_natural_earth_components_close_in_same_world():
    for country, ring, bounds in country_components():
        assert ring[0] == pytest.approx(ring[-1]), country.name
        assert bounds.longitude_span <= 360.000001
    antarctica = [bounds for country, ring, bounds in country_components() if country.name == 'Antarctica']
    assert max(bounds.longitude_span for bounds in antarctica) == pytest.approx(360)


def test_editor_projection_changes_persist_and_invalidate_cache(app, monkeypatch):
    from photoalbum.album.serialization import _instance_from_data, _instance_to_data
    from photoalbum.gui.preview_render_service import PreviewRenderService
    from photoalbum.templates.msb.geographic_map.settings import GeographicMapSettingsWidget
    import json

    register_discovered_template_extensions()
    requests = []
    monkeypatch.setattr(GeographicMapSettingsWidget, '_render_preview', lambda self: requests.append(True))
    original = PageInstance(template_id='geographic-map')
    translator = translator_for_template('geographic-map', Translator('en'))
    editor = GeographicMapSettingsWidget(original, photos_for(SCENARIOS['france']), translator=translator)
    try:
        instance = editor.instance()
        service = PreviewRenderService(translator)
        photos = photos_for(SCENARIOS['france'])
        before = service.key_for(instance, photos, page_width_mm=210, page_height_mm=297)
        editor._projection_combo.setCurrentIndex(editor._projection_combo.findData('equal_earth'))
        assert len(requests) == 2
        assert instance.settings['geographic_map']['projection'] == 'equal_earth'
        after = service.key_for(instance, photos, page_width_mm=210, page_height_mm=297)
        assert before != after
        restored = _instance_from_data(json.loads(json.dumps(_instance_to_data(instance))))
        assert restored == instance
        for language in ('fr', 'en'):
            tr = translator_for_template('geographic-map', Translator(language))
            assert tr.tr('page_settings.map_projection_web_mercator') == 'Web Mercator'
            assert tr.tr('page_settings.map_projection_equal_earth') == 'Equal Earth'
            assert tr.tr('page_settings.map_projection_robinson') == 'Robinson'
            assert tr.tr('page_settings.map_no_geographic_data') != 'page_settings.map_no_geographic_data'
    finally:
        editor.close()


@pytest.mark.parametrize('projection', map_painter.SUPPORTED_PROJECTIONS)
def test_neighbouring_land_is_painted_outside_photo_extent(app, projection):
    # A wide page shows more longitude than the fitted France photo extent.
    # Countries in that extra visible area must not become ocean.
    composition = compose_geographic_map(photos_for(SCENARIOS['france']))
    target = QRectF(0, 0, 1800, 850)
    image = QImage(1800, 850, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        map_painter.paint_geographic_map(painter, target, composition, projection=projection)
    finally:
        painter.end()
    fitted = map_painter._map_rect(composition.bounds, target, projection)
    for longitude, latitude in [(-7.5, 41.8), (14.5, 50), (16, 51.5)]:
        # Interior points in Portugal, Czechia and Poland, away from borders.
        assert not (composition.bounds.minimum_longitude <= longitude
                    <= composition.bounds.maximum_longitude)
        point = map_painter._project(longitude, latitude, composition.bounds, fitted, projection)
        assert target.contains(point)
        assert image.pixelColor(round(point.x()), round(point.y())) == map_painter.DEFAULT_LAND_COLOR
