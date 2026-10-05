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
    PhotoUsage,
    MetadataCandidates,
)
from photoalbum.metadata import FilenameDateParser

from .base import PhotoSource, SourceAsset
from .cache import SourceAssetCache
from .config import ProjectSource
from .metadata_policy import PhotoMetadataPolicy, resolve_photo_metadata


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
        metadata_policy: PhotoMetadataPolicy | None = None,
    ) -> SourceImportResult:
        assets = provider.list_assets(source.collection_id)
        effective_policy = metadata_policy or source.effective_metadata_policy
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
            photo = resolve_photo_metadata(photo, effective_policy)
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
        advertised = asset.advertised_candidates()
        dates = dict(advertised.date)
        filename_date = FilenameDateParser().parse(asset.filename)
        if filename_date is not None:
            dates.setdefault("filename", filename_date)
        locations = dict(advertised.location)
        if previous is not None:
            cached_geocoding = (
                previous.metadata_candidates.location.get("geocoding")
                or previous.geocoded_location_data
            )
            if cached_geocoding is not None:
                locations["geocoding"] = cached_geocoding
        candidates = MetadataCandidates(
            date=dates,
            gps=dict(advertised.gps),
            location=locations,
            caption=dict(advertised.caption),
        )

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

        initial_date_key = next(
            (key for key in ("provider", "exif", "filename") if key in dates),
            None,
        )
        asset_date_source = date_source_by_origin.get(
            "source" if initial_date_key == "provider" else initial_date_key,
            DateSource.UNKNOWN,
        )

        initial_gps_key = next(
            (key for key in ("provider", "exif") if key in advertised.gps),
            None,
        )
        asset_gps_source = gps_source_by_origin.get(
            "source" if initial_gps_key == "provider" else initial_gps_key,
            GpsSource.UNKNOWN,
        )

        capture_datetime = dates.get(initial_date_key) if initial_date_key else None
        date_source = asset_date_source
        initial_gps = advertised.gps.get(initial_gps_key) if initial_gps_key else None
        latitude = initial_gps.latitude if initial_gps else None
        longitude = initial_gps.longitude if initial_gps else None
        gps_source = asset_gps_source

        if previous is not None and (
            previous.manual_capture_datetime is not None
            or previous.date_source == DateSource.MANUAL
        ):
            capture_datetime = (
                previous.manual_capture_datetime or previous.capture_datetime
            )
            date_source = DateSource.MANUAL

        manual_gps = (
            previous is not None
            and (
                previous.manual_latitude is not None
                or previous.gps_source == GpsSource.MANUAL
            )
        )
        if manual_gps:
            latitude = previous.latitude
            longitude = previous.longitude
            gps_source = GpsSource.MANUAL

        exif_capture_datetime = dates.get("exif")
        source_capture_datetime = dates.get("provider")

        exif_gps = advertised.gps.get("exif")
        provider_gps = advertised.gps.get("provider")
        exif_latitude = exif_gps.latitude if exif_gps else None
        exif_longitude = exif_gps.longitude if exif_gps else None
        source_latitude = provider_gps.latitude if provider_gps else None
        source_longitude = provider_gps.longitude if provider_gps else None

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
            structured = locations.get("provider")
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
            usage=previous.usage if previous else PhotoUsage.BODY,
            imported_location_text=asset.location_text,
            imported_caption=candidates.caption.get("provider"),
            source_metadata=asset.metadata,
            metadata_candidates=candidates,
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
            original_capture_datetime=(
                dates.get(initial_date_key) if initial_date_key else None
            ),
            original_date_source=asset_date_source,
            original_latitude=(initial_gps.latitude if initial_gps else None),
            original_longitude=(initial_gps.longitude if initial_gps else None),
            manual_capture_datetime=(
                previous.manual_capture_datetime if previous else None
            ),
            manual_latitude=(previous.manual_latitude if previous else None),
            manual_longitude=(previous.manual_longitude if previous else None),
            manual_location_data=(
                previous.manual_location_data if previous else None
            ),
            exif_capture_datetime=exif_capture_datetime,
            source_capture_datetime=source_capture_datetime,
            exif_latitude=exif_latitude,
            exif_longitude=exif_longitude,
            source_latitude=source_latitude,
            source_longitude=source_longitude,
            source_location_data=locations.get("provider"),
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
