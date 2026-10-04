from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photoalbum.models import LocationComponent
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.models import Location, Photo
from photoalbum.geocoding import NominatimGeocoder, create_nominatim_location_resolver
from photoalbum.sources import (
    PhotoMetadataPolicy,
    PhotoSource,
    resolve_photo_metadata,
    ProjectSource,
    SourceAssetCache,
    SourceImporter,
    SourceImportResult,
)

from photoalbum.album import (
    AlbumStructureSettings,
    album_settings_from_json,
    album_settings_to_json,
)

class ProjectService:
    SOURCE_DIRECTORY_KEY = "source_directory"
    RECURSIVE_SCAN_KEY = "recursive_scan"
    ALBUM_STRUCTURE_SETTINGS_KEY = "album_structure_settings"
    PHOTO_SOURCE_KEY = "photo_source"
    PHOTO_METADATA_POLICY_KEY = "photo_metadata_policy"

    def __init__(self) -> None:
        self._database: ProjectDatabase | None = None
        # Authenticated providers are session-only. In particular, passwords
        # and session tokens are never serialized into the project database.
        self._source_sessions: dict[str, PhotoSource] = {}

    @property
    def is_open(self) -> bool:
        return self._database is not None

    @property
    def project_path(self) -> Path | None:
        if self._database is None:
            return None

        return self._database.path

    def create(self, path: Path) -> None:
        self.close()

        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        self._database = ProjectDatabase(path)
        self._database.initialize()

    def open(self, path: Path) -> None:
        self.close()

        path = path.expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Project does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Project path is not a file: {path}"
            )

        self._database = ProjectDatabase(path)
        self._database.initialize()

    def list_photos(self) -> list[Photo]:
        database = self._require_database()

        repository = PhotoRepository(database)

        return repository.list_all()

    def find_photo(self, photo_path: Path) -> Photo | None:
        repository = PhotoRepository(self._require_database())
        return repository.find_by_path(photo_path.expanduser().resolve())

    def find_photo_by_identity(self, identity: str) -> Photo | None:
        repository = PhotoRepository(self._require_database())
        return repository.find_by_identity(identity)

    def resolve_location(
        self,
        latitude: float,
        longitude: float,
        *,
        user_agent: str,
        endpoint: str = NominatimGeocoder.DEFAULT_ENDPOINT,
        language: str | None = None,
        force_refresh: bool = False,
    ) -> Location | None:
        """Resolve coordinates using the open project's geocoding cache."""
        resolver = create_nominatim_location_resolver(
            self._require_database(), user_agent=user_agent, endpoint=endpoint,
        )
        return resolver.resolve(
            latitude, longitude, language=language, force_refresh=force_refresh,
        )

    def restore_original_capture_datetime(
        self,
        photo_path: Path,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.restore_original_capture_datetime(
            photo_path
        )

    def set_manual_capture_datetime(
        self,
        photo_path: Path,
        capture_datetime: datetime,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.set_manual_capture_datetime(
            photo_path,
            capture_datetime,
        )

    def set_manual_gps(
        self,
        photo_path: Path,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.set_manual_gps(
            photo_path,
            latitude,
            longitude,
        )

    def restore_original_gps(
        self,
        photo_path: Path,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.restore_original_gps(
            photo_path
        )

    def set_photo_caption(
        self,
        photo_path: Path,
        caption: str | None,
    ) -> None:
        database = self._require_database()
        repository = PhotoRepository(database)

        repository.set_caption(
            photo_path,
            caption,
        )

    def set_editorial_location(
        self,
        photo_path: Path,
        *,
        components: tuple[LocationComponent, ...],
        location_text: str | None,
    ) -> None:
        database = self._require_database()
        repository = PhotoRepository(database)

        repository.set_editorial_location(
            photo_path,
            components=components,
            location_text=location_text,
        )

    def set_geocoded_location(
        self,
        photo_path: Path,
        *,
        place_name: str | None,
        city: str | None,
        address: str | None,
        raw_location_data: dict[str, object] | None = None,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.set_geocoded_location(
            photo_path,
            place_name=place_name,
            city=city,
            address=address,
            raw_location_data=raw_location_data,
        )

    def close(self) -> None:
        for provider in self._source_sessions.values():
            try:
                provider.close()
            except Exception:
                pass
        self._source_sessions.clear()
        if self._database is not None:
            self._database.close()
            self._database = None

    def set_source_directory(
        self,
        directory: Path,
    ) -> None:
        database = self._require_database()

        directory = directory.expanduser().resolve()

        database.set_project_metadata(
            self.SOURCE_DIRECTORY_KEY,
            str(directory),
        )
        database.set_project_metadata(
            self.PHOTO_SOURCE_KEY,
            ProjectSource(
                id="local",
                kind="local",
                name=directory.name,
                collection_id="folder",
                collection_name=directory.name,
                config={"directory": str(directory)},
            ).to_json(),
        )

    def get_source_directory(self) -> Path | None:
        database = self._require_database()

        value = database.get_project_metadata(
            self.SOURCE_DIRECTORY_KEY
        )

        if value is None:
            return None

        return Path(value)

    def set_photo_source(
        self, source: ProjectSource, provider: PhotoSource | None = None
    ) -> None:
        if source.kind != "local":
            raise RuntimeError(
                "Remote sources must be installed with change_photo_source()."
            )
        database = self._require_database()
        database.set_project_metadata(self.PHOTO_SOURCE_KEY, source.to_json())
        if provider is not None:
            old = self._source_sessions.pop(source.id, None)
            if old is not None and old is not provider:
                old.close()
            self._source_sessions[source.id] = provider

    def get_photo_source(self) -> ProjectSource | None:
        database = self._require_database()
        value = database.get_project_metadata(self.PHOTO_SOURCE_KEY)
        if value is not None:
            return ProjectSource.from_json(value)
        directory = self.get_source_directory()
        if directory is None:
            return None
        return ProjectSource(
            id="local", kind="local", name=directory.name,
            collection_id="folder", collection_name=directory.name,
            config={"directory": str(directory)},
        )

    def get_photo_metadata_policy(self) -> PhotoMetadataPolicy:
        """Return persisted metadata preferences or source-appropriate defaults."""
        database = self._require_database()
        value = database.get_project_metadata(
            self.PHOTO_METADATA_POLICY_KEY
        )
        if value is not None:
            return PhotoMetadataPolicy.from_json(value)

        source = self.get_photo_source()
        source_kind = source.kind if source is not None else "local"
        return PhotoMetadataPolicy.for_source_kind(source_kind)

    def set_photo_metadata_policy(
        self,
        policy: PhotoMetadataPolicy,
    ) -> None:
        """Persist metadata preferences without processing photos."""
        database = self._require_database()
        database.set_project_metadata(
            self.PHOTO_METADATA_POLICY_KEY,
            policy.to_json(),
        )

    def apply_photo_metadata_policy(
        self,
        policy: PhotoMetadataPolicy | None = None,
    ) -> None:
        """Recompute effective metadata from preserved candidates."""
        database = self._require_database()
        repository = PhotoRepository(database)

        if policy is None:
            policy = self.get_photo_metadata_policy()

        photos = repository.list_all()

        with repository.atomic():
            for photo in photos:
                repository.save(
                    resolve_photo_metadata(photo, policy),
                    commit=False,
                )

    def attach_source_session(self, source_id: str, provider: PhotoSource) -> None:
        self._require_database()
        old = self._source_sessions.pop(source_id, None)
        if old is not None and old is not provider:
            old.close()
        self._source_sessions[source_id] = provider

    def change_photo_source(
        self,
        source: ProjectSource,
        provider: PhotoSource,
    ) -> SourceImportResult:
        """Publish a new source only with its successfully imported snapshot."""
        database = self._require_database()
        importer = SourceImporter(
            PhotoRepository(database), SourceAssetCache(database.path)
        )
        try:
            result = importer.import_collection(
                source,
                provider,
                on_commit=lambda: database.set_project_metadata(
                    self.PHOTO_SOURCE_KEY,
                    source.to_json(),
                    commit=False,
                ),
            )
        except Exception:
            try:
                provider.close()
            except Exception:
                pass
            raise

        for source_id, previous in tuple(self._source_sessions.items()):
            if previous is provider:
                continue
            try:
                previous.close()
            except Exception:
                pass
            del self._source_sessions[source_id]
        self.attach_source_session(source.id, provider)
        return result

    def sync_photo_source(self) -> SourceImportResult:
        database = self._require_database()
        source = self.get_photo_source()
        if source is None:
            raise RuntimeError("No photo source is configured.")
        provider = self._source_sessions.get(source.id)
        if provider is None:
            raise RuntimeError(
                f"Source {source.name!r} must be connected before synchronization."
            )
        return SourceImporter(
            PhotoRepository(database), SourceAssetCache(database.path)
        ).import_collection(source, provider)

    def materialize_originals(self, photos: list[Photo]) -> None:
        database = self._require_database()
        cache = SourceAssetCache(database.path)
        for photo in photos:
            if photo.source_id == "local":
                photo.require_path()
                continue
            provider = self._source_sessions.get(photo.source_id)
            if provider is None:
                path = cache.path_for(photo, "original")
                marker = path.with_suffix(path.suffix + ".original")
                if marker.is_file():
                    photo.path = path
                    continue
                raise RuntimeError(
                    f"Source for {photo.filename!r} must be reconnected before export."
                )
            photo.path = cache.materialize(photo, provider, quality="original")

    def set_recursive_scan(
        self,
        recursive: bool,
    ) -> None:
        database = self._require_database()

        database.set_project_metadata(
            self.RECURSIVE_SCAN_KEY,
            "1" if recursive else "0",
        )

    def get_recursive_scan(self) -> bool:
        database = self._require_database()

        value = database.get_project_metadata(
            self.RECURSIVE_SCAN_KEY
        )

        return value == "1"


    def set_album_structure_settings(
        self,
        settings: AlbumStructureSettings,
    ) -> None:
        database = self._require_database()

        database.set_project_metadata(
            self.ALBUM_STRUCTURE_SETTINGS_KEY,
            album_settings_to_json(settings),
        )

    def get_album_structure_settings(
        self,
    ) -> AlbumStructureSettings | None:
        database = self._require_database()

        value = database.get_project_metadata(
            self.ALBUM_STRUCTURE_SETTINGS_KEY
        )

        if value is None:
            return None

        return album_settings_from_json(value)

    def _require_database(self) -> ProjectDatabase:
        if self._database is None:
            raise RuntimeError("No project is currently open.")

        return self._database
