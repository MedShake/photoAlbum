from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPSHandler, Request, build_opener

from photoalbum.models import GpsCandidate, MetadataCandidates

from .base import (
    AuthenticationError,
    SourceAsset,
    SourceCapabilities,
    SourceCollection,
    SourceError,
    copy_stream,
)


@dataclass(frozen=True)
class SynologyCredentials:
    """Ephemeral credentials used only to establish the DSM session."""

    username: str
    password: str = field(repr=False)
    otp_code: str | None = field(default=None, repr=False)


class SynologyPhotosSource:
    """Read-only adapter for Synology Photos' private WebAPI.

    All API names and response-shape knowledge intentionally live in this
    module because Synology does not publish a stable Photos API contract.
    """

    kind = "synology-photos"
    label = "Synology Photos"
    capabilities = SourceCapabilities(
        date_candidates=frozenset({"provider", "filename"}),
        gps_candidates=frozenset({"provider"}),
        location_candidates=frozenset({"provider"}),
        caption_candidates=frozenset({"provider"}),
        can_fetch_original=True,
    )
    PAGE_SIZE = 500
    ADDITIONAL = [
        "thumbnail", "resolution", "orientation", "exif", "description",
        "gps", "address", "provider_user_id",
    ]
    READ_ONLY_OPERATIONS = frozenset({
        ("SYNO.API.Auth", "login"),
        ("SYNO.API.Auth", "logout"),
        ("SYNO.Foto.UserInfo", "me"),
        ("SYNO.Foto.Browse.Album", "list"),
        ("SYNO.Foto.Browse.Item", "list"),
        ("SYNO.Foto.Thumbnail", "get"),
        ("SYNO.Foto.Download", "download"),
        ("SYNO.FotoTeam.Browse.Item", "list"),
        ("SYNO.FotoTeam.Thumbnail", "get"),
        ("SYNO.FotoTeam.Download", "download"),
    })

    def __init__(
        self,
        base_url: str,
        authentication: SynologyCredentials,
        *,
        verify_tls: bool = True,
        api_path: str = "/webapi/entry.cgi",
        opener=None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"

        self._credentials = authentication
        self._sid: str | None = None
        self._syno_token: str | None = None
        self._api_url = urljoin(
            self.base_url,
            api_path.lstrip("/") or "webapi/entry.cgi",
        )

        self._connected = False
        self.identity: str | None = None
        self._albums: dict[str, dict[str, Any]] = {}

        if opener is None:
            context = ssl.create_default_context()
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            opener = build_opener(
                HTTPSHandler(context=context)
            )
        self._opener = opener

    def connect(self) -> None:
        try:
            parameters: dict[str, object] = {
                "api": "SYNO.API.Auth",
                "version": 7,
                "method": "login",
                "account": self._credentials.username,
                "passwd": self._credentials.password,
                "session": "SynologyPhotos",
                "format": "sid",
                "enable_syno_token": "yes",
            }
            if self._credentials.otp_code:
                parameters["otp_code"] = self._credentials.otp_code

            auth_data = self._json_request(parameters, auth=False)
            sid = auth_data.get("sid")
            if not sid:
                raise AuthenticationError(
                    "Synology authentication returned no session id."
                )

            self._sid = str(sid)
            token = auth_data.get("synotoken")
            self._syno_token = str(token) if token else None

            data = self._json_request(
                {
                    "api": "SYNO.Foto.UserInfo",
                    "version": 1,
                    "method": "me",
                }
            )
        except SourceError as exc:
            raise AuthenticationError(str(exc)) from exc

        identity = (
            data.get("name")
            or data.get("username")
            or data.get("user_id")
            or data.get("id")
        )
        self.identity = str(identity) if identity is not None else None
        self._connected = True

    def list_collections(self) -> list[SourceCollection]:
        self._ensure_connected()
        rows = self._paged(
            api="SYNO.Foto.Browse.Album",
            version=1,
            parameters={"sort_by": "create_time", "sort_direction": "desc"},
        )
        # DSM releases differ on whether shared albums are included in the
        # default list. Querying the shared category is read-only and merging
        # by id makes both response behaviours deterministic.
        try:
            shared_rows = self._paged(
                api="SYNO.Foto.Browse.Album",
                version=1,
                parameters={"category": "shared"},
            )
        except SourceError:
            shared_rows = []
        # Some DSM builds ignore the shared-category filter and return albums
        # that were already present in the normal/owned listing. Never let such
        # duplicate shared rows overwrite the authoritative owned metadata.
        merged: list[tuple[dict[str, Any], str]] = []
        owned_ids: set[str] = set()

        for row in rows:
            album_id = row.get("id")
            if album_id is None:
                continue
            owned_ids.add(str(album_id))
            merged.append((dict(row), "owned"))

        for row in shared_rows:
            album_id = row.get("id")
            if album_id is None:
                continue
            if str(album_id) in owned_ids:
                continue
            merged.append((dict(row), "shared_with_me"))

        collections = []
        self._albums.clear()

        for row, relation in merged:
            album_id = row.get("id")
            if album_id is None:
                continue

            metadata = dict(row)
            metadata["_photoalbum_space"] = "personal"
            metadata["_photoalbum_relation"] = relation

            self._albums[str(album_id)] = metadata
            collections.append(SourceCollection(
                id=str(album_id),
                name=str(row.get("name") or album_id),
                item_count=_optional_int(row.get("item_count")),
                metadata=metadata,
            ))
        return collections

    def list_assets(self, collection_id: str) -> list[SourceAsset]:
        self._ensure_connected()
        album = self._albums.get(collection_id, {})
        team_space = album.get("_photoalbum_space") == "team"
        parameters: dict[str, object] = {
            "album_id": collection_id,
            "type": "photo",
            "sort_by": "takentime",
            "sort_direction": "asc",
            "additional": self.ADDITIONAL,
        }
        # A passphrase belongs to a true shared-with-me album. Metadata from
        # duplicate "shared" results must never alter an owned album request.
        if album.get("_photoalbum_relation") == "shared_with_me":
            passphrase = album.get("passphrase") or album.get("sharing_id")
            if passphrase:
                parameters["passphrase"] = passphrase

        api = (
            "SYNO.FotoTeam.Browse.Item"
            if team_space
            else "SYNO.Foto.Browse.Item"
        )
        rows = self._paged(
            api=api,
            version=1,
            parameters=parameters,
        )
        result = []
        for row in rows:
            if row.get("id") is None:
                continue
            row = dict(row)
            row["_photoalbum_space"] = "team" if team_space else "personal"
            result.append(self._asset_from_row(row))
        return result

    def fetch_thumbnail(self, asset: SourceAsset, destination: Path) -> Path:
        additional = _mapping(asset.metadata.get("additional"))
        thumbnail = _mapping(additional.get("thumbnail"))
        cache_key = thumbnail.get("cache_key") or asset.metadata.get("cache_key")
        prefix = self._api_prefix(asset)
        params: dict[str, object] = {
            "api": f"{prefix}.Thumbnail",
            "version": 2,
            "method": "get",
            "id": asset.id,
            "type": "unit",
            "size": "xl",
        }
        if cache_key is not None:
            params["cache_key"] = cache_key
        return self._download(params, destination)

    def fetch_original(self, asset: SourceAsset, destination: Path) -> Path:
        additional = _mapping(asset.metadata.get("additional"))
        thumbnail = _mapping(additional.get("thumbnail"))
        cache_key = thumbnail.get("cache_key") or asset.metadata.get("cache_key")
        prefix = self._api_prefix(asset)
        params: dict[str, object] = {
            "api": f"{prefix}.Download",
            "version": 1,
            "method": "download",
            "unit_id": [int(asset.id) if asset.id.isdigit() else asset.id],
        }
        if cache_key is not None:
            params["cache_key"] = cache_key
        return self._download(params, destination)

    def close(self) -> None:
        # A direct DSM login belongs to Photo-Album, so explicitly close it.
        if self._credentials is not None and self._sid is not None:
            try:
                self._json_request(
                    {
                        "api": "SYNO.API.Auth",
                        "version": 7,
                        "method": "logout",
                        "session": "SynologyPhotos",
                    }
                )
            except SourceError:
                pass

        self._connected = False
        self.identity = None
        self._credentials = None
        self._session = None
        self._sid = None
        self._syno_token = None
        self._api_url = None

    def _paged(
        self, *, api: str, version: int, parameters: dict[str, object]
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self._json_request(
                {
                    "api": api, "version": version, "method": "list",
                    "offset": offset, "limit": self.PAGE_SIZE, **parameters,
                },
            )
            page = data.get("list") or []
            rows.extend(dict(row) for row in page)
            if len(page) < self.PAGE_SIZE:
                break
            offset += len(page)
        return rows

    def _asset_from_row(self, row: dict[str, Any]) -> SourceAsset:
        additional = _mapping(row.get("additional"))
        resolution = _mapping(additional.get("resolution"))
        gps = _mapping(additional.get("gps"))
        thumbnail = _mapping(additional.get("thumbnail"))
        timestamp = row.get("time") or row.get("takentime")
        description = additional.get("description")
        if isinstance(description, dict):
            description = description.get("description") or description.get("text")
        address = additional.get("address")
        structured_location = None
        if isinstance(address, dict):
            raw_address = dict(address)

            component_keys = (
                "house_number",
                "road",
                "suburb",
                "neighbourhood",
                "city_district",
                "city",
                "town",
                "village",
                "municipality",
                "county",
                "state",
                "postcode",
                "country",
            )

            components: list[dict[str, str]] = []
            seen_values: set[str] = set()
            for key in component_keys:
                value = address.get(key)
                if value is None:
                    continue
                text_value = str(value).strip()
                if not text_value:
                    continue
                normalized = text_value.casefold()
                if normalized in seen_values:
                    continue
                seen_values.add(normalized)
                components.append({"key": key, "value": text_value})

            city = next(
                (
                    str(address[key]).strip()
                    for key in ("city", "town", "village", "municipality")
                    if address.get(key)
                ),
                None,
            )

            place_name = next(
                (
                    str(address[key]).strip()
                    for key in (
                        "attraction",
                        "tourism",
                        "amenity",
                        "historic",
                        "building",
                        "name",
                    )
                    if address.get(key)
                ),
                None,
            )

            location_text = (
                address.get("formatted")
                or address.get("display_name")
            )
            if location_text is not None:
                location_text = str(location_text).strip() or None

            if location_text is None:
                location_text = ", ".join(
                    component["value"] for component in components
                ) or None

            structured_location = {
                "provider": "synology",
                "place_name": place_name,
                "city": city,
                "address": location_text,
                "components": components,
                "raw": raw_address,
            }
        else:
            location_text = str(address).strip() if address else None
            if location_text:
                structured_location = {
                    "provider": "synology",
                    "place_name": None,
                    "city": None,
                    "address": location_text,
                    "components": [],
                    "raw": address,
                }

        capture_datetime = _timestamp(timestamp)
        latitude = _optional_float(gps.get("latitude"))
        longitude = _optional_float(gps.get("longitude"))
        caption = str(description) if description else (
            str(row["title"]) if row.get("title") else None
        )

        width = _optional_int(resolution.get("width"))
        height = _optional_int(resolution.get("height"))
        orientation = _optional_int(additional.get("orientation"))
        # Synology Photos reports resolution in visual orientation while also
        # retaining the original EXIF orientation. SourceAsset follows the
        # local-source convention: raw dimensions + EXIF orientation.
        if orientation in (5, 6, 7, 8) and width is not None and height is not None:
            width, height = height, width

        return SourceAsset(
            id=str(row["id"]),
            filename=str(row.get("filename") or row["id"]),
            capture_datetime=capture_datetime,
            capture_datetime_origin="source",
            file_size=_optional_int(row.get("filesize")),
            width=width,
            height=height,
            orientation=orientation,
            latitude=latitude,
            longitude=longitude,
            gps_origin="source",
            title=str(row["title"]) if row.get("title") else None,
            description=str(description) if description else None,
            location_text=location_text,
            structured_location=structured_location,
            revision=str(
                thumbnail.get("cache_key")
                or row.get("indexed_time")
                or ""
            ) or None,
            metadata=dict(row),
            candidates=MetadataCandidates(
                date=(
                    {"provider": capture_datetime}
                    if capture_datetime is not None
                    else {}
                ),
                gps=(
                    {"provider": GpsCandidate(latitude, longitude)}
                    if latitude is not None and longitude is not None
                    else {}
                ),
                location=(
                    {"provider": structured_location}
                    if structured_location is not None
                    else {}
                ),
                caption=(
                    {"provider": caption}
                    if caption
                    else {}
                ),
            ),
        )

    @staticmethod
    def _api_prefix(asset: SourceAsset) -> str:
        return (
            "SYNO.FotoTeam"
            if asset.metadata.get("_photoalbum_space") == "team"
            else "SYNO.Foto"
        )

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()

    def _encoded(self, parameters: dict[str, object], *, auth: bool = True) -> bytes:
        values = dict(parameters)
        if auth and self._sid:
            values["_sid"] = self._sid
        for key, value in tuple(values.items()):
            if isinstance(value, (list, dict, tuple)):
                values[key] = json.dumps(value, separators=(",", ":"))
        return urlencode(values).encode("utf-8")

    def _open(self, parameters: dict[str, object], *, auth=True):
        self._enforce_read_only(parameters)
        if self._api_url is None:
            raise AuthenticationError("The Synology session is closed.")

        request = Request(
            self._api_url,
            data=self._encoded(parameters, auth=auth),
            method="POST",
        )


        if auth and self._syno_token:
            request.add_header("X-SYNO-TOKEN", self._syno_token)

        try:
            return self._opener.open(request, timeout=30)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"Synology Photos request failed: {exc}") from exc

    @classmethod
    def _enforce_read_only(cls, parameters: dict[str, object]) -> None:
        operation = (
            str(parameters.get("api", "")),
            str(parameters.get("method", "")),
        )
        if operation not in cls.READ_ONLY_OPERATIONS:
            raise SourceError(
                "Synology Photos operation blocked by the read-only policy: "
                f"{operation[0]}.{operation[1]}"
            )

    def _json_request(
        self, parameters: dict[str, object], *, auth=True
    ) -> dict[str, Any]:
        with self._open(parameters, auth=auth) as response:
            try:
                payload = json.load(response)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourceError("Synology Photos returned invalid JSON.") from exc
        if not payload.get("success"):
            error = payload.get("error") or {}
            code = error.get("code", "unknown") if isinstance(error, dict) else error
            raise SourceError(f"Synology Photos API error {code}.")
        return dict(payload.get("data") or {})

    def _download(
        self, parameters: dict[str, object], destination: Path
    ) -> Path:
        self._ensure_connected()
        with self._open(parameters) as response:
            return copy_stream(response, destination)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.isdigit():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
