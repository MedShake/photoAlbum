from __future__ import annotations

import shutil
from pathlib import Path

from photoalbum.metadata import FilenameDateParser, PhotoAnalyzer
from photoalbum.models import GpsCandidate, MetadataCandidates
from photoalbum.scanner import FolderScanner

from .base import SourceAsset, SourceCapabilities, SourceCollection


class LocalFolderSource:
    kind = "local"
    label = "Local folder"
    capabilities = SourceCapabilities(
        date_candidates=frozenset({"exif", "filename"}),
        gps_candidates=frozenset({"exif"}),
        can_fetch_original=True,
    )

    def __init__(self, directory: Path, *, recursive: bool = False) -> None:
        self.directory = directory.expanduser().resolve()
        self.recursive = recursive

    def list_collections(self) -> list[SourceCollection]:
        return [SourceCollection(id="folder", name=self.directory.name)]

    def list_assets(self, collection_id: str = "folder") -> list[SourceAsset]:
        if collection_id != "folder":
            raise KeyError(collection_id)
        analyzer = PhotoAnalyzer()
        filename_parser = FilenameDateParser()
        return [
            SourceAsset(
                id=str(path), filename=photo.filename,
                capture_datetime=photo.capture_datetime,
                capture_datetime_origin=photo.date_source.value,
                file_size=photo.file_size, width=photo.width, height=photo.height,
                orientation=photo.orientation, latitude=photo.latitude,
                longitude=photo.longitude,
                gps_origin="exif" if photo.has_gps else "unknown",
                revision=f"{photo.modified_time_ns}:{photo.file_size}",
                metadata={"path": str(path)},
                candidates=MetadataCandidates(
                    date={
                        **(
                            {"exif": photo.capture_datetime}
                            if photo.capture_datetime is not None
                            and photo.date_source.value == "exif"
                            else {}
                        ),
                        **(
                            {"filename": filename_date}
                            if filename_date is not None
                            else {}
                        ),
                    },
                    gps=(
                        {
                            "exif": GpsCandidate(
                                photo.latitude,
                                photo.longitude,
                            )
                        }
                        if photo.has_gps
                        else {}
                    ),
                ),
            )
            for path in FolderScanner().scan(self.directory, recursive=self.recursive)
            for photo in [analyzer.analyze(path)]
            for filename_date in [filename_parser.parse(path.name)]
        ]

    def fetch_thumbnail(self, asset: SourceAsset, destination: Path) -> Path:
        return self.fetch_original(asset, destination)

    def fetch_original(self, asset: SourceAsset, destination: Path) -> Path:
        source = Path(str(asset.metadata["path"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def close(self) -> None:
        return None
