from __future__ import annotations

from dataclasses import replace
from uuid import uuid4
from datetime import datetime
from pathlib import Path

from photoalbum.models import LocationComponent, PhotoUsage
from photoalbum.database.source_repository import SourceRepository
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.models import Location, Photo
from photoalbum.geocoding import NominatimGeocoder, create_nominatim_location_resolver
from photoalbum.project_metadata import (
    PdfExportSettings,
    pdf_export_settings_from_json,
    pdf_export_settings_to_json,
)
from photoalbum.sources import (
    PhotoMetadataPolicy,
    PhotoSource,
    resolve_photo_metadata,
    ProjectSource,
    SourceAssetCache,
    SourceImporter,
    SourceImportResult,
    SourceCapabilities,
    SourceReconnectRequiredError,
)
from photoalbum.sources.base import SourceError
from photoalbum.sources.operation import SourceOperationResult

from photoalbum.album import (
    AlbumStructureSettings,
    album_settings_from_json,
    album_settings_to_json,
)

class ProjectService:
    ALBUM_STRUCTURE_SETTINGS_KEY = "album_structure_settings"
    PROJECT_NAME_KEY = "project_name"
    PDF_EXPORT_SETTINGS_KEY = "pdf_export_settings"

    def __init__(self) -> None:
        self._database: ProjectDatabase | None = None
        # Authenticated providers are session-only. In particular, passwords
        # and session tokens are never serialized into the project database.
        self._source_sessions: dict[str, PhotoSource] = {}
        self._source_results: dict[str, SourceOperationResult] = {}
        self._asset_cache = None
        self._cache_lease = None
        self._external_asset_lease = None

    def _open_cache(self) -> None:
        self._asset_cache = SourceAssetCache(
            self._database.path, project_id=self._database.get_project_metadata("cache_project_id")
        )
        self._cache_lease = self._asset_cache.manager.protect(
            self._asset_cache.project_id, light_only=True
        )
        self._cache_lease.__enter__()
        self._asset_cache.manager.enforce_quota()

    def retain_cached_originals(self) -> bool:
        """Retain until project close; return whether this call acquired the lease."""
        if self._external_asset_lease is None:
            lease = self._asset_cache.manager.protect(self._asset_cache.project_id)
            lease.__enter__()
            self._external_asset_lease = lease
            return True
        return False

    def release_cached_originals(self) -> None:
        """Release a newly acquired lease when opening an external viewer fails."""
        lease = self._external_asset_lease
        if lease is not None:
            self._external_asset_lease = None
            lease.__exit__(None, None, None)

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
        self.set_project_name(path.stem)
        self._open_cache()

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

        self._open_cache()

    def list_photos(self) -> list[Photo]:
        database = self._require_database()

        repository = PhotoRepository(database)

        active = {source.id: source for source in self.list_sources() if source.enabled}
        photos = [photo for photo in repository.list_all() if photo.source_id in active]
        for photo in photos:
            if active[photo.source_id].kind != "local":
                # Persisted paths may refer to an old adjacent cache or another OS.
                photo.path = (self._asset_cache.cached_path(photo, "thumbnail")
                              or self._asset_cache.path_for(photo, "thumbnail"))
        return photos

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
        photo_path: Path | str,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.restore_original_capture_datetime(
            photo_path
        )

    def set_manual_capture_datetime(
        self,
        photo_path: Path | str,
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
        photo_path: Path | str,
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
        photo_path: Path | str,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.restore_original_gps(
            photo_path
        )

    def set_photo_caption(
        self,
        photo_path: Path | str,
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
        photo_path: Path | str,
        *,
        components: tuple[LocationComponent, ...],
        location_text: str | None,
        manual_location_data_override: dict[str, object] | None = None,
    ) -> None:
        database = self._require_database()
        repository = PhotoRepository(database)

        repository.set_editorial_location(
            photo_path,
            components=components,
            location_text=location_text,
            manual_location_data_override=manual_location_data_override,
        )

    def set_geocoded_location(
        self,
        photo_path: Path | str,
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
        self._source_results.clear()
        if self._database is not None:
            self._database.close()
            self._database = None
        for name in ("_external_asset_lease", "_cache_lease"):
            lease = getattr(self, name)
            if lease is not None:
                setattr(self, name, None)
                lease.__exit__(None, None, None)
        self._asset_cache = None

    def list_sources(self) -> list[ProjectSource]:
        return SourceRepository(self._require_database()).list_all()

    def get_photo_source(self, source_id: str | None = None) -> ProjectSource | None:
        repository = SourceRepository(self._require_database())
        if source_id is not None:
            return repository.find(source_id)
        sources = repository.list_all()
        return sources[0] if sources else None

    def set_photo_source(self, source: ProjectSource, provider: PhotoSource | None = None) -> None:
        SourceRepository(self._require_database()).save(source)
        if provider is not None:
            self.attach_source_session(source.id, provider)

    def add_local_source(self, directory: Path, *, recursive: bool = False) -> ProjectSource:
        directory = directory.expanduser().resolve()
        source = ProjectSource(
            id=uuid4().hex, kind="local", name=directory.name,
            collection_id="folder", collection_name=directory.name,
            config={"directory": str(directory), "recursive": recursive},
            provider_label="Local folder",
            capabilities=SourceCapabilities(
                date_candidates=frozenset({"exif", "filename"}),
                gps_candidates=frozenset({"exif"}), can_fetch_original=True),
        )
        self.set_photo_source(source)
        return source

    def set_source_enabled(self, source_id: str, enabled: bool) -> None:
        SourceRepository(self._require_database()).set_enabled(source_id, enabled)

    def delete_source(self, source_id: str) -> None:
        SourceRepository(self._require_database()).delete(source_id)
        self._asset_cache.manager.purge(self._asset_cache.project_id, source_id)
        provider = self._source_sessions.pop(source_id, None)
        if provider is not None:
            provider.close()

    def set_source_directory(self, directory: Path, source_id: str | None = None) -> None:
        source = self.get_photo_source(source_id)
        if source is None or source.kind != "local":
            self.add_local_source(directory)
            return
        directory = directory.expanduser().resolve()
        self.set_photo_source(replace(
            source, name=directory.name, collection_name=directory.name,
            config={**source.config, "directory": str(directory)}))

    def get_source_directory(self, source_id: str | None = None) -> Path | None:
        source = self.get_photo_source(source_id)
        return (Path(str(source.config["directory"]))
                if source is not None and source.kind == "local" else None)

    def get_photo_metadata_policy(self, source_id: str | None = None) -> PhotoMetadataPolicy:
        source = self.get_photo_source(source_id)
        return source.effective_metadata_policy if source else PhotoMetadataPolicy.for_source_kind("local")

    def set_photo_metadata_policy(self, policy: PhotoMetadataPolicy, source_id: str | None = None) -> None:
        source = self.get_photo_source(source_id)
        if source is None:
            raise KeyError(source_id)
        self.set_photo_source(replace(source, metadata_policy=policy))

    def apply_photo_metadata_policy(self, policy: PhotoMetadataPolicy | None = None,
                                    source_id: str | None = None) -> None:
        repository = PhotoRepository(self._require_database())
        sources = ([self.get_photo_source(source_id)] if source_id is not None
                   else self.list_sources())
        with repository.atomic():
            for source in sources:
                if source is None:
                    continue
                for photo in repository.list_by_source(source.id):
                    repository.save(resolve_photo_metadata(
                        photo, policy or source.effective_metadata_policy), commit=False)

    def preview_photo_metadata_policy(self, policy: PhotoMetadataPolicy | None = None,
                                      source_id: str | None = None) -> list[Photo]:
        sources = {source.id: source for source in self.list_sources()}
        return [
            resolve_photo_metadata(photo, policy or sources[photo.source_id].effective_metadata_policy)
            if source_id is None or photo.source_id == source_id else photo
            for photo in self.list_photos()
        ]

    def list_album_photos(self) -> list[Photo]:
        return [photo for photo in self.list_photos() if photo.usage != PhotoUsage.OFF]

    def list_body_photos(self) -> list[Photo]:
        return [photo for photo in self.list_photos() if photo.usage == PhotoUsage.BODY]

    def set_photo_usage(self, identity: str, usage: PhotoUsage) -> None:
        PhotoRepository(self._require_database()).set_usage(identity, usage)

    def source_labels(self) -> dict[str, str]:
        return {source.id: self.get_source_label(source.id) for source in self.list_sources()}

    def get_source_label(self, source_id: str | None = None) -> str:
        source = self.get_photo_source(source_id)
        if source is None:
            return ""
        provider = self._source_sessions.get(source.id)
        return str(getattr(provider, "label", None) or source.provider_label or source.kind.title())

    def available_metadata_candidates(self, source_id: str | None = None) -> dict[str, set[str]]:
        available = {key: set() for key in ("date", "gps", "location", "caption")}
        source = self.get_photo_source(source_id)
        if source is None:
            return available
        photos = PhotoRepository(self._require_database()).list_by_source(source.id)
        for photo in photos:
            for key in available:
                available[key].update(getattr(photo.metadata_candidates, key))
        capabilities = source.capabilities or getattr(self._source_sessions.get(source.id), "capabilities", None)
        if capabilities is not None:
            for key in available:
                available[key].update(getattr(capabilities, key + "_candidates"))
        return available

    def get_photo_source_session(
        self,
        source_id: str,
    ) -> PhotoSource | None:
        """Return the in-memory provider session for a configured source."""
        self._require_database()
        provider = self._source_sessions.get(source_id)
        if getattr(provider, "session_invalid", False) is True:
            return None
        result = self._source_results.get(source_id)
        if result is not None and result.issue == "authentication":
            return None
        return provider

    def record_source_result(self, result: SourceOperationResult) -> None:
        self._source_results[result.source_id] = result

    def source_status(self, source: ProjectSource) -> str | None:
        result = self._source_results.get(source.id)
        if source.kind == "local":
            import os
            try:
                with os.scandir(str(source.config["directory"])):
                    pass
            except OSError:
                return "unavailable"
        else:
            provider = self._source_sessions.get(source.id)
            if (getattr(provider, "session_invalid", False) is True
                    or (result is not None and result.issue == "authentication")):
                return "invalid_session"
            if provider is None:
                photos = PhotoRepository(self._require_database()).list_by_source(source.id)
                for photo in photos:
                    thumbnail = self._asset_cache.path_for(photo, "thumbnail")
                    try:
                        if not thumbnail.is_file() or thumbnail.stat().st_size <= 0:
                            return "disconnected_missing_images"
                    except OSError:
                        return "disconnected_missing_images"
                return "disconnected"
        if result is not None and result.status != "success":
            if result.issue == "geocoding":
                return "geocoding"
            if result.issue == "access":
                return "unavailable"
            return result.status
        return None

    def attach_source_session(self, source_id: str, provider: PhotoSource) -> None:
        self._require_database()
        old = self._source_sessions.pop(source_id, None)
        if old is not None and old is not provider:
            old.close()
        self._source_sessions[source_id] = provider
        self._source_results.pop(source_id, None)

    def activate_source_session(self, source_id: str, provider: PhotoSource) -> None:
        self.attach_source_session(source_id, provider)

    def change_photo_source(self, source: ProjectSource, provider: PhotoSource) -> SourceImportResult:
        database = self._require_database()
        try:
            result = SourceImporter(PhotoRepository(database), SourceAssetCache(database.path)).import_collection(
                source, provider, metadata_policy=source.effective_metadata_policy,
                on_commit=lambda: SourceRepository(database).save(source, commit=False))
        except Exception:
            provider.close()
            raise
        self.attach_source_session(source.id, provider)
        return result

    def sync_photo_source(self, source_id: str | None = None) -> SourceImportResult:
        database = self._require_database()
        source = self.get_photo_source(source_id)
        if source is None:
            raise RuntimeError("No photo source is configured.")
        provider = self._source_sessions.get(source.id)
        if provider is None:
            raise RuntimeError(f"Source {source.name!r} must be connected before synchronization.")
        return SourceImporter(PhotoRepository(database), SourceAssetCache(database.path)).import_collection(
            source, provider, metadata_policy=source.effective_metadata_policy)

    def materialize_originals(self, photos: list[Photo]) -> None:
        database = self._require_database()
        cache = SourceAssetCache(database.path)
        # PDF preparation runs in a worker: read source descriptors using a
        # connection owned by that thread, never the GUI connection.
        reader = ProjectDatabase(database.path)
        try:
            sources = {source.id: source for source in SourceRepository(reader).list_all()}
        finally:
            reader.close()
        for photo in photos:
            source = sources.get(photo.source_id)
            if source is not None and source.kind == "local":
                photo.require_path()
                continue
            provider = self.get_photo_source_session(photo.source_id)
            if provider is None:
                path = cache.cached_path(photo, "original")
                if path is not None:
                    photo.path = path
                    continue
                raise SourceReconnectRequiredError(
                    filename=photo.filename,
                    source_id=photo.source_id,
                    operation="export",
                )
            try:
                photo.path = cache.materialize(photo, provider, quality="original")
            except SourceReconnectRequiredError:
                self.record_source_result(SourceOperationResult(
                    photo.source_id, "failed", "authentication",
                ))
                raise
            except SourceError as exc:
                self.record_source_result(SourceOperationResult(
                    photo.source_id, "failed", "access", str(exc),
                ))
                raise

    def set_recursive_scan(self, recursive: bool, source_id: str | None = None) -> None:
        source = self.get_photo_source(source_id)
        if source is None:
            raise KeyError(source_id)
        self.set_photo_source(replace(source, config={**source.config, "recursive": recursive}))

    def get_recursive_scan(self, source_id: str | None = None) -> bool:
        source = self.get_photo_source(source_id)
        return bool(source and source.config.get("recursive", False))


    def get_project_name(self) -> str:
        database = self._require_database()
        value = database.get_project_metadata(self.PROJECT_NAME_KEY)
        if value is not None and value.strip():
            return value.strip()
        project_path = self.project_path
        return project_path.stem if project_path is not None else ""

    def set_project_name(self, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Project name cannot be empty.")
        self._require_database().set_project_metadata(
            self.PROJECT_NAME_KEY, normalized
        )

    def set_pdf_export_settings(self, settings: PdfExportSettings) -> None:
        self._require_database().set_project_metadata(
            self.PDF_EXPORT_SETTINGS_KEY,
            pdf_export_settings_to_json(settings),
        )

    def get_pdf_export_settings(self) -> PdfExportSettings | None:
        value = self._require_database().get_project_metadata(
            self.PDF_EXPORT_SETTINGS_KEY
        )
        if value is None:
            return None
        return pdf_export_settings_from_json(value)

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
