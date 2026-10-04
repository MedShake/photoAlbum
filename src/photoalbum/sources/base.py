from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class SourceCollection:
    id: str
    name: str
    item_count: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceAsset:
    """Provider-neutral snapshot of an asset exposed by a collection."""

    id: str
    filename: str
    capture_datetime: datetime | None = None
    capture_datetime_origin: str = "source"
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    orientation: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    gps_origin: str = "source"
    title: str | None = None
    description: str | None = None
    location_text: str | None = None
    structured_location: dict[str, object] | None = None
    revision: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class PhotoSource(Protocol):
    """Read-only boundary implemented by local and remote photo services."""

    kind: str

    def list_collections(self) -> list[SourceCollection]: ...

    def list_assets(self, collection_id: str) -> list[SourceAsset]: ...

    def fetch_thumbnail(self, asset: SourceAsset, destination: Path) -> Path: ...

    def fetch_original(self, asset: SourceAsset, destination: Path) -> Path: ...

    def close(self) -> None: ...


class SourceError(RuntimeError):
    pass


class AuthenticationError(SourceError):
    pass


def copy_stream(source: BinaryIO, destination: Path) -> Path:
    """Atomically copy a provider response into the project cache."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.part")
    try:
        with temporary.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
