from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from photoalbum.database import PhotoRepository
from photoalbum.models import (
    DateSource,
    GpsSource,
    LocationSource,
    Photo,
)

from .base import PhotoSource, SourceAsset
from .cache import SourceAssetCache
from .config import ProjectSource


@dataclass(frozen=True)
class SourceImportResult:
    photos: tuple[Photo, ...]
    added: int
    updated: int
    missing: int


class SourceImporter:
    """Create an explicit project snapshot from a provider collection."""

    def __init__(self, repository: PhotoRepository, cache: SourceAssetCache) -> None:
        self._repository = repository
        self._cache = cache

    def import_collection(
        self,
        source: ProjectSource,
        provider: PhotoSource,
        *,
        on_progress: Callable[[int, int], None] | None = None,
        on_commit: Callable[[], None] | None = None,
    ) -> SourceImportResult:
        assets = provider.list_assets(source.collection_id)
        known = {
            photo.identity: photo
            for photo in self._repository.list_by_source(
                source.id, include_missing=True
            )
        }
        imported: list[Photo] = []
        seen: set[str] = set()
        added = updated = 0
        for index, asset in enumerate(assets, start=1):
            identity = f"{source.id}:{asset.id}"
            previous = known.get(identity)
            photo = self._photo_from_asset(source.id, asset, previous)
            thumbnail = self._cache.materialize(
                photo, provider, quality="thumbnail"
            )
            photo.path = thumbnail
            imported.append(photo)
            seen.add(identity)
            if previous is None:
                added += 1
            else:
                updated += 1
            if on_progress is not None:
                on_progress(index, len(assets))

        missing_identities = [
            identity for identity in known if identity not in seen
        ]
        with self._repository.atomic():
            self._repository.set_other_sources_missing(source.id, commit=False)
            for photo in imported:
                self._repository.save(photo, commit=False)
            for identity in missing_identities:
                self._repository.set_missing_by_identity(
                    identity, True, commit=False
                )
            if on_commit is not None:
                on_commit()
        missing = len(missing_identities)
        imported.sort(key=lambda photo: (
            photo.capture_datetime is None,
            photo.capture_datetime,
            photo.filename.lower(),
        ))
        return SourceImportResult(tuple(imported), added, updated, missing)

    @staticmethod
    def _photo_from_asset(
        source_id: str, asset: SourceAsset, previous: Photo | None
    ) -> Photo:
        date_source_by_origin = {
            "exif": DateSource.EXIF,
            "source": DateSource.SOURCE,
            "filename": DateSource.FILENAME,
            "unknown": DateSource.UNKNOWN,
        }
        gps_source_by_origin = {
            "exif": GpsSource.EXIF,
            "source": GpsSource.SOURCE,
            "unknown": GpsSource.UNKNOWN,
        }

        asset_date_source = date_source_by_origin.get(
            asset.capture_datetime_origin,
            DateSource.UNKNOWN,
        )
        if asset.capture_datetime is None:
            asset_date_source = DateSource.UNKNOWN

        asset_gps_source = gps_source_by_origin.get(
            asset.gps_origin,
            GpsSource.UNKNOWN,
        )
        if asset.latitude is None or asset.longitude is None:
            asset_gps_source = GpsSource.UNKNOWN

        capture_datetime = asset.capture_datetime
        date_source = asset_date_source
        latitude = asset.latitude
        longitude = asset.longitude
        gps_source = asset_gps_source

        if previous is not None and previous.date_source == DateSource.MANUAL:
            capture_datetime = previous.capture_datetime
            date_source = DateSource.MANUAL

        manual_gps = (
            previous is not None
            and (
                previous.gps_source == GpsSource.MANUAL
                or previous.location_source == LocationSource.MANUAL
            )
        )
        if manual_gps:
            latitude = previous.latitude
            longitude = previous.longitude
            gps_source = GpsSource.MANUAL

        exif_capture_datetime = (
            asset.capture_datetime
            if asset.capture_datetime_origin == "exif"
            else previous.exif_capture_datetime if previous else None
        )
        source_capture_datetime = (
            asset.capture_datetime
            if asset.capture_datetime_origin == "source"
            else previous.source_capture_datetime if previous else None
        )

        exif_latitude = (
            asset.latitude
            if asset.gps_origin == "exif"
            else previous.exif_latitude if previous else None
        )
        exif_longitude = (
            asset.longitude
            if asset.gps_origin == "exif"
            else previous.exif_longitude if previous else None
        )
        source_latitude = (
            asset.latitude
            if asset.gps_origin == "source"
            else previous.source_latitude if previous else None
        )
        source_longitude = (
            asset.longitude
            if asset.gps_origin == "source"
            else previous.source_longitude if previous else None
        )

        place_name = previous.place_name if previous else None
        city = previous.city if previous else None
        address = previous.address if previous else None
        raw_location_data = previous.raw_location_data if previous else None
        location_source = (
            previous.location_source
            if previous
            else LocationSource.UNKNOWN
        )

        if not (
            previous is not None
            and previous.location_source == LocationSource.MANUAL
        ):
            structured = asset.structured_location
            if structured is not None:
                place_name = _optional_text(structured.get("place_name"))
                city = _optional_text(structured.get("city"))
                address = _optional_text(structured.get("address"))
                raw_location_data = None
                location_source = LocationSource.SOURCE

        return Photo(
            path=previous.path if previous is not None else None,
            filename=asset.filename,
            source_id=source_id,
            asset_id=asset.id,
            imported_location_text=asset.location_text,
            imported_caption=asset.description or asset.title,
            source_metadata=asset.metadata,
            file_size=asset.file_size,
            content_hash=asset.revision,
            width=asset.width,
            height=asset.height,
            orientation=asset.orientation,
            capture_datetime=capture_datetime,
            date_source=date_source,
            latitude=latitude,
            longitude=longitude,
            gps_source=gps_source,
            original_orientation=asset.orientation,
            original_capture_datetime=asset.capture_datetime,
            original_date_source=asset_date_source,
            original_latitude=asset.latitude,
            original_longitude=asset.longitude,
            exif_capture_datetime=exif_capture_datetime,
            source_capture_datetime=source_capture_datetime,
            exif_latitude=exif_latitude,
            exif_longitude=exif_longitude,
            source_latitude=source_latitude,
            source_longitude=source_longitude,
            source_location_data=asset.structured_location,
            geocoded_location_data=(
                previous.geocoded_location_data if previous else None
            ),
            place_name=place_name,
            city=city,
            address=address,
            raw_location_data=raw_location_data,
            location_source=location_source,
            selected_location_components=(
                previous.selected_location_components if previous else ()
            ),
            location_text=previous.location_text if previous else None,
            location_selection_edited=(
                previous.location_selection_edited if previous else False
            ),
            caption=previous.caption if previous else None,
        )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
