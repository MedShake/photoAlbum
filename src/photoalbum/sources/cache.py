from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from photoalbum.models import Photo

from .base import PhotoSource, SourceAsset
from .errors import SourceReconnectRequiredError


class SourceAssetCache:
    """Project-scoped cache for provider thumbnails and original files."""

    def __init__(self, project_path: Path) -> None:
        project_path = project_path.expanduser().resolve()
        self.root = project_path.parent / f".{project_path.name}.cache" / "assets"

    def path_for(self, photo: Photo, quality: str) -> Path:
        if quality not in {"thumbnail", "original"}:
            raise ValueError(f"Unsupported asset quality: {quality}")
        digest = sha256(photo.identity.encode("utf-8")).hexdigest()
        suffix = Path(photo.filename).suffix.lower() or ".jpg"
        # A stable canonical path keeps existing renderer contracts intact.
        # The thumbnail initially occupies it; requesting the original upgrades
        # that cache entry atomically without changing Photo.path.
        return self.root / digest[:2] / digest / f"asset{suffix}"

    def materialize(
        self,
        photo: Photo,
        provider: PhotoSource,
        *,
        quality: str,
    ) -> Path:
        destination = self.path_for(photo, quality)
        original_marker = destination.with_suffix(destination.suffix + ".original")
        revision_file = destination.with_suffix(destination.suffix + ".revision")
        expected_revision = photo.content_hash or ""
        try:
            cached_revision = revision_file.read_text(encoding="utf-8")
        except OSError:
            cached_revision = None
        if (
            destination.is_file()
            and destination.stat().st_size > 0
            and cached_revision == expected_revision
            and (quality == "thumbnail" or original_marker.is_file())
        ):
            return destination
        if cached_revision != expected_revision:
            original_marker.unlink(missing_ok=True)
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
        if quality == "thumbnail":
            path = provider.fetch_thumbnail(asset, destination)
            revision_file.write_text(expected_revision, encoding="utf-8")
            return path
        path = provider.fetch_original(asset, destination)
        revision_file.write_text(expected_revision, encoding="utf-8")
        original_marker.touch()
        return path

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
                path = self.path_for(photo, quality)
                if not path.is_file():
                    raise SourceReconnectRequiredError(
                        filename=photo.filename,
                        source_id=photo.source_id,
                        operation="retrieve",
                    )
            else:
                path = self.materialize(photo, provider, quality=quality)
            prepared.append(replace(photo, path=path))
        return prepared
