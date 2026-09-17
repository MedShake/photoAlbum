import sqlite3
from datetime import datetime
from types import SimpleNamespace

import pytest

from photoalbum import __version__, cli
from photoalbum.app import project_service
from photoalbum.album.composition import photo_location_text
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import GeocodingError
from photoalbum.models import DateSource, Location, LocationComponent, Photo


@pytest.fixture
def project(tmp_path):
    path = tmp_path / 'album.photoalbum'
    source = tmp_path / 'photo.jpg'
    source.write_bytes(b'unchanged source image')
    db = ProjectDatabase(path)
    db.initialize()
    PhotoRepository(db).save(Photo(
        path=source, filename=source.name,
        capture_datetime=datetime(2020, 1, 1), date_source=DateSource.EXIF,
        latitude=48, longitude=2, city='Old city',
        raw_location_data={'address': {'city': 'Old city'}},
        location_text='Editorial place', location_selection_edited=True,
        selected_location_components=(LocationComponent(key='city', value='Editorial place'),),
        caption='Free caption',
    ))
    db.close()
    yield path, source
    assert source.read_bytes() == b'unchanged source image'


def run(monkeypatch, project, *arguments):
    path, source = project
    monkeypatch.setattr('sys.argv', ['photo-album-cli', arguments[0], str(source),
                                      *arguments[1:], '--project', str(path)])
    return cli.main()


def read(project):
    db = ProjectDatabase(project[0])
    try:
        return PhotoRepository(db).find_by_path(project[1])
    finally:
        db.close()


@pytest.mark.parametrize('value,code', [('2025-07-14 18:30:00', 0), ('bad', 2),
                                       ('2025-07-14T18:30:00+02:00', 2)])
def test_date(monkeypatch, project, value, code):
    assert run(monkeypatch, project, 'set-date', value) == code
    photo = read(project)
    assert photo.capture_datetime == (datetime(2025, 7, 14, 18, 30) if code == 0
                                      else datetime(2020, 1, 1))
    assert photo.original_capture_datetime == datetime(2020, 1, 1)
    assert photo.caption == 'Free caption'
    if code == 0:
        assert photo.date_source == DateSource.MANUAL


@pytest.mark.parametrize('command', ['set-gps', 'refresh-location'])
@pytest.mark.parametrize('outcome', ['success', 'missing', 'error'])
def test_geocoding(monkeypatch, project, command, outcome, capsys):
    calls = []
    connections = []
    original_connect = sqlite3.connect

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', connect)

    def resolve(lat, lon, **kwargs):
        calls.append((lat, lon, kwargs))
        if outcome == 'error':
            raise GeocodingError('offline')
        if outcome == 'missing':
            return None
        return Location(latitude=lat, longitude=lon, city='New city',
                        raw_data={'address': {'city': 'New city'}})
    def factory(database, **kwargs):
        assert kwargs['user_agent'] == f'PhotoAlbum/{__version__}'
        if command == 'set-gps':
            assert PhotoRepository(database).find_by_path(project[1]).raw_location_data is None
        return SimpleNamespace(resolve=resolve)
    monkeypatch.setattr(project_service, 'create_nominatim_location_resolver', factory)
    extra = ('45', '4') if command == 'set-gps' else ()
    assert run(monkeypatch, project, command, *extra) == (0 if outcome == 'success' else 1)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connections[0].execute('SELECT 1')
    photo = read(project)
    assert (photo.latitude, photo.longitude) == ((45, 4) if extra else (48, 2))
    assert calls[0][2] == {'language': 'fr', 'force_refresh': command == 'refresh-location'}
    expected = 'New city' if outcome == 'success' else 'Old city'
    if extra and outcome != 'success':
        assert photo.raw_location_data is None
        assert 'remain saved' in capsys.readouterr().err
    else:
        assert photo.raw_location_data == {'address': {'city': expected}}
    assert photo.caption == 'Free caption'
    assert photo_location_text(photo) == 'Editorial place'
    assert photo.selected_location_components == (LocationComponent(key='city', value='Editorial place'),)
    assert (photo.original_latitude, photo.original_longitude) == (48, 2)


@pytest.mark.parametrize('lat,lon', [('91', '2'), ('45', '181'), ('nan', '2')])
def test_invalid_gps_does_not_change_project(monkeypatch, project, lat, lon):
    assert run(monkeypatch, project, 'set-gps', lat, lon) == 2
    assert read(project).raw_location_data == {'address': {'city': 'Old city'}}
    assert read(project).latitude == 48


@pytest.mark.parametrize('arguments,expected', [
    (('--text', 'Chosen place'), 'Chosen place'),
    (('--text', ''), None),
    (('--place', 'Tower', '--city', 'Paris'), 'Tower, Paris'),
])
def test_editorial_location(monkeypatch, project, arguments, expected):
    assert run(monkeypatch, project, 'set-location', *arguments) == 0
    photo = read(project)
    assert photo_location_text(photo) == expected
    assert photo.caption == 'Free caption'
    assert photo.raw_location_data == {'address': {'city': 'Old city'}}
    assert (photo.latitude, photo.longitude) == (48, 2)


def test_missing_project_is_not_created(monkeypatch, tmp_path):
    project = (tmp_path / 'missing.photoalbum', tmp_path / 'photo.jpg')
    assert run(monkeypatch, project, 'set-gps', '45', '4') == 2
    assert not project[0].exists()


def test_unknown_photo(monkeypatch, project):
    missing = (project[0], project[1].with_name('unknown.jpg'))
    assert run(monkeypatch, missing, 'set-gps', '45', '4') == 2
    assert read(project).latitude == 48
