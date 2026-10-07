from pathlib import Path

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.gui.workers.metadata_refresh_worker import MetadataRefreshWorker
from photoalbum.models import LocationSource, Photo
from photoalbum.sources import PhotoMetadataPolicy
from photoalbum.geocoding.location_resolver import (
    LocationResolution,
    LocationResolutionSource,
)
from photoalbum.models import Location


def test_disabled_nominatim_keeps_cached_candidate_without_network(
    tmp_path: Path,
    monkeypatch,
):
    project_path = tmp_path / "metadata-worker.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    path = tmp_path / "photo.jpg"
    PhotoRepository(database).save(
        Photo(
            path=path,
            filename=path.name,
            latitude=47.2184,
            longitude=-1.5536,
            exif_latitude=47.2184,
            exif_longitude=-1.5536,
            geocoded_location_data={
                "provider": "nominatim",
                "latitude": 47.2184,
                "longitude": -1.5536,
                "city": "Nantes",
                "address": "Nantes, France",
            },
        )
    )
    database.close()

    def unexpected_network(*args, **kwargs):
        raise AssertionError("Nominatim resolver must not be created")

    monkeypatch.setattr(
        "photoalbum.gui.workers.metadata_refresh_worker.create_nominatim_location_resolver",
        unexpected_network,
    )
    worker = MetadataRefreshWorker(
        project_path=project_path,
        policy=PhotoMetadataPolicy(
            date_preference="exif",
            gps_preference="exif",
            location_preference="geocoding",
            nominatim_enabled=False,
        ),
        language="en",
        user_agent="tests",
    )
    failed = []
    completed = []
    phases = []
    worker.failed.connect(failed.append)
    worker.completed.connect(completed.append)
    worker.phase_progress.connect(phases.append)

    worker.run()

    assert failed == []
    assert len(completed) == 1
    assert completed[0][0].city == "Nantes"
    assert completed[0][0].location_source == LocationSource.GEOCODING
    assert {progress.phase.value for progress in phases} == {"metadata"}


def test_nominatim_progress_counts_only_eligible_photos(tmp_path: Path, monkeypatch):
    project_path = tmp_path / "eligible.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    repository = PhotoRepository(database)
    for index, cached in enumerate((True, False), start=1):
        latitude = 47.0 + index
        repository.save(
            Photo(
                path=tmp_path / f"{index}.jpg",
                filename=f"{index}.jpg",
                latitude=latitude,
                longitude=2.0,
                exif_latitude=latitude,
                exif_longitude=2.0,
                geocoded_location_data=(
                    {
                        "provider": "nominatim",
                        "latitude": latitude,
                        "longitude": 2.0,
                        "city": "Cached",
                    }
                    if cached
                    else None
                ),
            )
        )
    database.close()

    class Resolver:
        def resolve_with_source(self, latitude, longitude, **kwargs):
            return LocationResolution(
                Location(latitude, longitude, city="Resolved"),
                LocationResolutionSource.REVERSE,
            )

    monkeypatch.setattr(
        "photoalbum.gui.workers.metadata_refresh_worker.create_nominatim_location_resolver",
        lambda *args, **kwargs: Resolver(),
    )
    worker = MetadataRefreshWorker(
        project_path=project_path,
        policy=PhotoMetadataPolicy(
            date_preference="exif",
            gps_preference="exif",
            location_preference="geocoding",
            nominatim_enabled=True,
        ),
        language="en",
        user_agent="tests",
    )
    phases = []
    worker.phase_progress.connect(phases.append)
    worker.run()

    nominatim = [item for item in phases if item.phase.value == "nominatim"]
    assert [(item.current, item.total) for item in nominatim] == [(0, 1), (1, 1)]


def test_nominatim_network_error_reports_unsuccessful_geocoding(tmp_path: Path, monkeypatch):
    from photoalbum.geocoding import GeocodingError

    project_path = tmp_path / "geocoding-error.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    PhotoRepository(database).save(
        Photo(
            path=tmp_path / "photo.jpg",
            filename="photo.jpg",
            latitude=47.2184,
            longitude=-1.5536,
            exif_latitude=47.2184,
            exif_longitude=-1.5536,
        )
    )
    database.close()

    class Resolver:
        def resolve_with_source(self, *args, **kwargs):
            raise GeocodingError("offline")

    monkeypatch.setattr(
        "photoalbum.gui.workers.metadata_refresh_worker.create_nominatim_location_resolver",
        lambda *args, **kwargs: Resolver(),
    )
    worker = MetadataRefreshWorker(
        project_path=project_path,
        policy=PhotoMetadataPolicy(
            date_preference="exif",
            gps_preference="exif",
            location_preference="none",
            nominatim_enabled=True,
        ),
        language="en",
        user_agent="tests",
    )
    statuses = []
    completed = []
    worker.geocoding_status.connect(statuses.append)
    worker.completed.connect(completed.append)

    worker.run()

    assert statuses == [False]
    assert len(completed) == 1
