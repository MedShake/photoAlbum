"""Canonical normalization of the published v0.1.0 schema and dev snapshots.

This operates inside ProjectDatabase's migration transaction. Historical
columns are inputs, never alternate persistent sources of configuration.
"""
from __future__ import annotations

import json
from pathlib import Path


def normalize_photo(row: dict, *, source_id: str, kind: str) -> dict:
    row = dict(row)
    row.setdefault("source_id", source_id)
    row.setdefault("asset_id", row["path"])
    row.setdefault("asset_key", f'{row["source_id"]}:{row["asset_id"]}')
    origin = "exif" if kind == "local" else "source"
    if row.get("original_date_source") == "exif" or origin == "source":
        row.setdefault(f"{origin}_capture_datetime", row.get("original_capture_datetime"))
    for axis in ("latitude", "longitude"):
        row.setdefault(f"{origin}_{axis}", row.get(f"original_{axis}"))
    row.setdefault("gps_source", "unknown" if row.get("latitude") is None else
                   "manual" if row.get("location_source") == "manual" else origin)
    if row.get("location_source") == "geocoding" and not row.get("geocoded_location_data"):
        row["geocoded_location_data"] = json.dumps({
            "provider": "nominatim", "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            **{key: row.get(key) for key in ("place_name", "city", "address")},
            "raw": json.loads(row["raw_location_data"]) if row.get("raw_location_data") else None,
        })
    candidates = json.loads(row.get("metadata_candidates") or "{}")
    dates = candidates.setdefault("date", {})
    gps = candidates.setdefault("gps", {})
    locations = candidates.setdefault("location", {})
    captions = candidates.setdefault("caption", {})
    for prefix, key in (("exif", "exif"), ("source", "provider")):
        if row.get(f"{prefix}_capture_datetime"):
            dates.setdefault(key, row[f"{prefix}_capture_datetime"])
        if all(row.get(f"{prefix}_{axis}") is not None for axis in ("latitude", "longitude")):
            gps.setdefault(key, {axis: row[f"{prefix}_{axis}"] for axis in ("latitude", "longitude")})
    if row.get("original_date_source") == "filename" and row.get("original_capture_datetime"):
        dates.setdefault("filename", row["original_capture_datetime"])
    for column, key in (("source_location_data", "provider"), ("geocoded_location_data", "geocoding")):
        if row.get(column):
            locations.setdefault(key, json.loads(row[column]))
    if row.get("imported_caption"):
        captions.setdefault("provider", row["imported_caption"])
    row["metadata_candidates"] = json.dumps(candidates, ensure_ascii=False)
    if row.get("date_source") == "manual":
        row.setdefault("manual_capture_datetime", row.get("capture_datetime"))
    if row.get("gps_source") == "manual":
        for axis in ("latitude", "longitude"):
            row.setdefault(f"manual_{axis}", row.get(axis))
    if not row.get("manual_location_data") and (
        row.get("location_source") == "manual" or row.get("location_selection_edited")
    ):
        row["manual_location_data"] = json.dumps({
            **{key: row.get(key) for key in ("place_name", "city", "address")},
            "address": row.get("location_text") if row.get("location_selection_edited") else row.get("address"),
            "components": json.loads(row.get("selected_location_components") or "[]"),
            "raw": json.loads(row["raw_location_data"]) if row.get("raw_location_data") else None,
        }, ensure_ascii=False)
    row.setdefault("usage", "body")
    return row


def normalize_project(database) -> None:
    from photoalbum.sources.config import ProjectSource
    from photoalbum.sources.metadata_policy import PhotoMetadataPolicy
    from .source_repository import SourceRepository

    connection = database.connection
    photos = [dict(row) for row in connection.execute("SELECT * FROM photos")]
    raw_source = database.get_project_metadata("photo_source")
    directory = database.get_project_metadata("source_directory")
    policy = database.get_project_metadata("photo_metadata_policy")
    recursive = database.get_project_metadata("recursive_scan") == "1"
    sources = SourceRepository(database)
    if raw_source:
        source_data = json.loads(raw_source)
        source_data["metadata_policy"] = json.loads(policy) if policy else source_data.get("metadata_policy")
        if source_data["kind"] == "local":
            source_data.setdefault("config", {})["recursive"] = recursive
        source = ProjectSource.from_json(json.dumps(source_data))
        sources.save(source, commit=False)
    elif directory or photos:
        folder = Path(directory) if directory else Path(photos[0]["path"]).parent
        source = ProjectSource(
            id="local", kind="local", name=folder.name,
            collection_id="folder", collection_name=folder.name,
            config={"directory": str(folder), "recursive": recursive},
            provider_label="Local folder",
            metadata_policy=PhotoMetadataPolicy.from_json(policy) if policy else None,
        )
        sources.save(source, commit=False)
    else:
        source = None
    # Development projects can contain retained snapshots of former sources.
    # Keep these independently addressable without guessing a provider from ID.
    for row in photos:
        source_id = row.get("source_id") or (source.id if source else "local")
        if sources.find(source_id) is None:
            sources.save(ProjectSource(
                id=source_id, kind="snapshot", name=source_id,
                collection_id="snapshot", collection_name=source_id,
                provider_label="Snapshot",
            ), commit=False)

    connection.execute("ALTER TABLE photos RENAME TO photos_legacy")
    database._create_photos_table()
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(photos)")}
    for row in photos:
        source_id = row.get("source_id") or (source.id if source else "local")
        configured = sources.find(source_id)
        normalized = normalize_photo(row, source_id=source_id, kind=configured.kind)
        keys = [key for key in normalized if key in columns]
        connection.execute(
            f'INSERT INTO photos ({", ".join(keys)}) VALUES ({", ".join("?" for _ in keys)})',
            [normalized[key] for key in keys],
        )
    connection.execute("DROP TABLE photos_legacy")
    connection.execute(
        "DELETE FROM project_metadata WHERE key IN ('photo_source', 'photo_metadata_policy', 'source_directory', 'recursive_scan')")
