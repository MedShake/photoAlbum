from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from sqlite3 import OperationalError

from photoalbum.cache_manager import CacheManager
from photoalbum.database import ProjectDatabase
from photoalbum.models import Photo

from .base import PhotoSource, SourceAsset, AuthenticationError
from .errors import SourceReconnectRequiredError


class SourceAssetCache:
    """Project-scoped cache for provider thumbnails and original files."""

    def __init__(self, project_path: Path, *, project_id: str | None = None) -> None:
        if project_id is None:
            database = ProjectDatabase(project_path.expanduser().resolve())
            try:
                try:
                    project_id = database.get_project_metadata("cache_project_id")
                except OperationalError:
                    project_id = None
                if project_id is None:
                    database.initialize()
                    project_id = database.get_project_metadata("cache_project_id")
            finally:
                database.close()
        self.project_id = project_id
        self.manager = CacheManager()
        self.root = self.manager.project_directory(self.project_id)

    def path_for(self, photo: Photo, quality: str) -> Path:
        if quality not in {"thumbnail", "original"}:
            raise ValueError(f"Unsupported asset quality: {quality}")
        digest = sha256((photo.identity + "\0" + (photo.content_hash or "")).encode("utf-8")).hexdigest()
        suffix = Path(photo.filename).suffix.lower() or ".jpg"
        return self.manager.source_directory(self.project_id, photo.source_id) / quality / digest / f"asset{suffix}"

    def cached_path(self, photo: Photo, quality: str) -> Path | None:
        path = self.path_for(photo, quality)
        if path.is_file() and path.stat().st_size > 0:
            self.manager.touch(path)
            return path
        return None

    def materialize(
        self,
        photo: Photo,
        provider: PhotoSource,
        *,
        quality: str,
    ) -> Path:
        destination = self.path_for(photo, quality)
        asset = SourceAsset(
            id=photo.asset_id or photo.identity,
            filename=photo.filename,
            capture_datetime=photo.original_capture_datetime,
            file_size=photo.file_size,
            width=photo.width,
            height=photo.height,
            orientation=photo.original_orientation,
            latitude=photo.original_latitude,
            longitude=photo.original_longitude,
            description=photo.imported_caption,
            location_text=photo.imported_location_text,
            revision=photo.content_hash,
            metadata=photo.source_metadata or {},
            candidates=photo.metadata_candidates,
        )
        with self.manager.protect(trim=False):
            cached = self.cached_path(photo, quality)
            if cached is not None:
                return cached
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Publish only complete files; a failed download must not look cached.
            # Keep the staging file one directory above the content digest. This
            # leaves enough path-length headroom on Windows for providers such
            # as Synology that perform their own atomic ``.part`` write.
            from uuid import uuid4
            staging_directory = destination.parent.parent
            temporary = staging_directory / f".{uuid4().hex}{destination.suffix}"
            try:
                fetch = provider.fetch_thumbnail if quality == "thumbnail" else provider.fetch_original
                fetched = Path(fetch(asset, temporary))
                if fetched != temporary:
                    # Local providers may return their original instead of copying.
                    from shutil import copyfile
                    copyfile(fetched, temporary)
                temporary.replace(destination)
            except AuthenticationError as exc:
                if quality != "original":
                    raise
                raise SourceReconnectRequiredError(
                    filename=photo.filename, source_id=photo.source_id,
                ) from exc
            finally:
                temporary.unlink(missing_ok=True)
        self.manager.enforce_quota(exclude=(destination,))
        return destination

    def renderer_photos(
        self,
        photos: list[Photo] | tuple[Photo, ...],
        providers: dict[str, PhotoSource],
        *,
        quality: str,
        source_kinds: dict[str, str] | None = None,
    ) -> list[Photo]:
        prepared = []
        for photo in photos:
            provider = providers.get(photo.source_id)
            kind = (source_kinds or {}).get(photo.source_id, getattr(provider, "kind", None))
            if kind == "local" or photo.asset_id is None:
                photo.require_path()
                prepared.append(photo)
                continue
            provider = providers.get(photo.source_id)
            if provider is None:
                path = self.cached_path(photo, quality)
                if path is None:
                    raise SourceReconnectRequiredError(
                        filename=photo.filename,
                        source_id=photo.source_id,
                        operation="retrieve",
                    )
            else:
                path = self.materialize(photo, provider, quality=quality)
            prepared.append(replace(photo, path=path))
        return prepared
