from __future__ import annotations

from io import BytesIO
import json
from urllib.parse import parse_qs

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.gui.synology_source_dialog import SynologySourceDialog
from photoalbum.i18n import Translator
from photoalbum.sources import (
    ProjectSource,
    SourceCollection,
    SourceError,
    SynologyCredentials,
    SynologyPhotosSource,
)


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((
            request.full_url,
            parse_qs(request.data.decode()),
            dict(request.header_items()),
        ))
        payload = self.payloads.pop(0)
        if isinstance(payload, bytes):
            return Response(payload)
        return Response(json.dumps(payload).encode())



@pytest.mark.parametrize(
    ("width", "height", "orientation", "expected"),
    [
        (4032, 3024, 1, (4032, 3024)),
        (4032, 3024, 3, (4032, 3024)),
        (3024, 4032, 5, (4032, 3024)),
        (3024, 4032, 6, (4032, 3024)),
        (3024, 4032, 7, (4032, 3024)),
        (3024, 4032, 8, (4032, 3024)),
        (4384, 2192, 6, (2192, 4384)),
    ],
)
def test_synology_normalizes_visual_resolution_to_raw_exif_dimensions(
    width, height, orientation, expected
):
    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials("alice", "secret"),
        opener=FakeOpener([]),
    )
    asset = source._asset_from_row({
        "id": 42,
        "filename": "IMG_0042.JPG",
        "filesize": 123,
        "time": 1720000000,
        "additional": {
            "thumbnail": {"cache_key": "42_7", "xl": "ready"},
            "resolution": {"width": width, "height": height},
            "orientation": orientation,
        },
    })

    assert (asset.width, asset.height) == expected
    assert asset.orientation == orientation


def test_synology_lists_albums_and_maps_asset_metadata(tmp_path):
    opener = FakeOpener([
        {"success": True, "data": {"sid": "direct-session", "synotoken": "direct-token"}},
        {"success": True, "data": {"name": "alice"}},
        {"success": True, "data": {"list": [
            {"id": 7, "name": "Summer", "item_count": 1}
        ]}},
        {"success": True, "data": {"list": []}},
        {"success": True, "data": {"list": [{
            "id": 42,
            "filename": "IMG_0042.JPG",
            "filesize": 123,
            "time": 1720000000,
            "additional": {
                "thumbnail": {"cache_key": "42_7", "xl": "ready"},
                "resolution": {"width": 4000, "height": 3000},
                "orientation": 1,
                "gps": {"latitude": 48.1, "longitude": 2.3},
                "description": "A title",
                "address": {
                    "display_name": "Rue Exemple, Paris, France",
                    "road": "Rue Exemple",
                    "city": "Paris",
                    "state": "Île-de-France",
                    "country": "France",
                    "country_name": "France",
                },
            },
        }]}},
        b"thumbnail bytes",
        b"original bytes",
        {"success": True},
    ])
    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials("alice", "secret"),
        opener=opener,
    )
    albums = source.list_collections()
    assets = source.list_assets(albums[0].id)
    asset = assets[0]
    assert albums[0].name == "Summer"
    assert asset.id == "42"
    assert (asset.width, asset.height) == (4000, 3000)
    assert (asset.latitude, asset.longitude) == (48.1, 2.3)
    assert asset.description == "A title"
    assert asset.location_text == "Rue Exemple, Paris, France"
    assert asset.capture_datetime_origin == "source"
    assert asset.gps_origin == "source"
    assert asset.structured_location is not None
    assert asset.structured_location["provider"] == "synology"
    assert asset.structured_location["city"] == "Paris"
    assert asset.structured_location["address"] == "Rue Exemple, Paris, France"
    assert asset.structured_location["components"] == [
        {"key": "road", "value": "Rue Exemple"},
        {"key": "city", "value": "Paris"},
        {"key": "state", "value": "Île-de-France"},
        {"key": "country", "value": "France"},
    ]
    assert asset.revision == "42_7"

    thumbnail = source.fetch_thumbnail(asset, tmp_path / "thumb.jpg")
    original = source.fetch_original(asset, tmp_path / "original.jpg")
    assert thumbnail.read_bytes() == b"thumbnail bytes"
    assert original.read_bytes() == b"original bytes"
    source.close()

    login = opener.requests[0][1]
    assert login["api"] == ["SYNO.API.Auth"]
    assert login["method"] == ["login"]
    identity = opener.requests[1][1]
    assert identity["api"] == ["SYNO.Foto.UserInfo"]
    assert identity["method"] == ["me"]
    assert all(
        url == "https://nas.example/webapi/entry.cgi"
        for url, _, _ in opener.requests
    )
    headers = {
        key.casefold(): value for key, value in opener.requests[1][2].items()
    }
    assert headers["x-syno-token"] == "direct-token"
    item_request = opener.requests[4][1]
    assert item_request["album_id"] == ["7"]
    assert "gps" in item_request["additional"][0]
    assert opener.requests[5][1]["api"] == ["SYNO.Foto.Thumbnail"]
    assert opener.requests[6][1]["api"] == ["SYNO.Foto.Download"]


def test_synology_read_only_policy_blocks_mutation_before_network():
    opener = FakeOpener([])
    source = SynologyPhotosSource(
        "https://nas.example/", SynologyCredentials("alice", "secret"), opener=opener
    )
    with pytest.raises(SourceError, match="read-only policy"):
        source._json_request({
            "api": "SYNO.Foto.Browse.Album",
            "version": 1,
            "method": "delete",
            "id": 7,
        })
    assert opener.requests == []



class _DialogProvider:
    def __init__(self, *, fail_listing=False, albums=None):
        self.fail_listing = fail_listing
        self.albums = list(albums or [])
        self.connected = False
        self.closed = False
        self.list_calls = 0
        self.identity = "alice"

    def connect(self):
        self.connected = True

    def list_collections(self):
        self.list_calls += 1
        if self.fail_listing:
            raise RuntimeError("listing failed")
        return self.albums

    def close(self):
        self.closed = True


def test_dialog_closes_session_when_album_listing_fails():
    QApplication.instance() or QApplication([])
    provider = _DialogProvider(fail_listing=True)
    dialog = SynologySourceDialog(
        Translator("en"),
        provider_factory=lambda *args, **kwargs: provider,
    )
    dialog._connect()
    assert provider.connected is True
    assert provider.list_calls == 1
    assert provider.closed is True
    assert dialog.provider is None
    dialog.close()


def test_reconnect_dialog_does_not_list_collections():
    QApplication.instance() or QApplication([])
    provider = _DialogProvider()
    existing = ProjectSource(
        id="synology-1", kind="synology-photos", name="NAS",
        collection_id="7", collection_name="Summer",
        config={"base_url": "https://nas.example", "username": "alice"},
    )
    dialog = SynologySourceDialog(
        Translator("en"),
        provider_factory=lambda *args, **kwargs: provider,
        existing_source=existing,
    )
    dialog._connect()
    assert provider.connected is True
    assert provider.list_calls == 0
    assert dialog.source == existing
    dialog.reject()
    assert provider.closed is True



def test_new_source_persists_endpoint_without_credentials_secrets():
    QApplication.instance() or QApplication([])
    provider = _DialogProvider(
        albums=[SourceCollection(id="7", name="Summer", item_count=1)]
    )
    dialog = SynologySourceDialog(
        Translator("en"),
        provider_factory=lambda *args, **kwargs: provider,
    )
    dialog.url_edit.setText("https://nas.example")
    dialog.username_edit.setText("alice")
    dialog.password_edit.setText("secret-password")
    dialog.otp_edit.setText("123456")
    dialog._connect()
    dialog._accept_source()

    serialized = dialog.source.to_json()
    assert dialog.source.config == {
        "base_url": "https://nas.example",
        "api_path": "/webapi/entry.cgi",
        "username": "alice",
        "verify_tls": True,
    }
    assert "secret-password" not in serialized
    assert "123456" not in serialized
    provider.close()


def test_synology_occurrences_are_unique_and_collection_edits_keep_identity():
    from dataclasses import replace
    from photoalbum.sources import PhotoMetadataPolicy
    QApplication.instance() or QApplication([])
    albums = [SourceCollection(id="7", name="Summer"), SourceCollection(id="8", name="Winter")]
    sources = []
    for _ in range(2):
        provider = _DialogProvider(albums=albums)
        dialog = SynologySourceDialog(Translator("en"),
            provider_factory=lambda *args, **kwargs: provider)
        dialog.url_edit.setText("https://nas.example")
        dialog._connect()
        dialog._accept_source()
        sources.append(dialog.source)
        provider.close()
    assert sources[0].id != sources[1].id
    original = replace(sources[0], enabled=False,
        metadata_policy=PhotoMetadataPolicy("filename", "exif", "none", False))
    provider = _DialogProvider(albums=albums)
    editor = SynologySourceDialog(Translator("en"), existing_source=original, edit_collection=True,
        provider_factory=lambda *args, **kwargs: provider)
    editor._connect()
    assert editor.album_combo.currentData().id == original.collection_id
    editor.album_combo.setCurrentIndex(1)
    editor._accept_source()
    assert editor.source.id == original.id
    assert editor.source.collection_id == "8"
    assert editor.source.metadata_policy == original.metadata_policy
    assert editor.source.enabled is False
    provider.close()


def test_legacy_project_source_with_username_config_still_loads():
    source = ProjectSource.from_json(json.dumps({
        "schema_version": 1,
        "id": "synology-legacy",
        "kind": "synology-photos",
        "name": "NAS",
        "collection_id": "7",
        "collection_name": "Summer",
        "config": {
            "base_url": "https://nas.example",
            "username": "alice",
            "verify_tls": True,
        },
    }))
    assert source.config["username"] == "alice"



def test_synology_direct_auth_uses_token_header_not_form_body():
    opener = FakeOpener([
        {
            "success": True,
            "data": {
                "sid": "direct-session",
                "synotoken": "direct-token",
            },
        },
        {
            "success": True,
            "data": {
                "name": "alice",
            },
        },
        {
            "success": True,
            "data": {},
        },
    ])

    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials(
            username="alice",
            password="secret",
        ),
        opener=opener,
    )

    source.connect()

    login_url, login_body, login_headers = opener.requests[0]
    assert login_url == "https://nas.example/webapi/entry.cgi"
    assert login_body["api"] == ["SYNO.API.Auth"]
    assert login_body["version"] == ["7"]
    assert login_body["method"] == ["login"]
    assert login_body["account"] == ["alice"]
    assert login_body["passwd"] == ["secret"]
    assert login_body["enable_syno_token"] == ["yes"]
    assert "_sid" not in login_body
    assert "SynoToken" not in login_body
    assert "x-syno-token" not in {
        key.casefold(): value for key, value in login_headers.items()
    }

    _, identity_body, identity_headers = opener.requests[1]
    normalized_headers = {
        key.casefold(): value
        for key, value in identity_headers.items()
    }

    assert identity_body["api"] == ["SYNO.Foto.UserInfo"]
    assert identity_body["method"] == ["me"]
    assert identity_body["_sid"] == ["direct-session"]

    # This is the real-NAS regression contract:
    # the token is a HTTP header, never a form field.
    assert "SynoToken" not in identity_body
    assert normalized_headers["x-syno-token"] == "direct-token"

    source.close()

    _, logout_body, logout_headers = opener.requests[2]
    normalized_logout_headers = {
        key.casefold(): value
        for key, value in logout_headers.items()
    }
    assert logout_body["api"] == ["SYNO.API.Auth"]
    assert logout_body["method"] == ["logout"]
    assert logout_body["_sid"] == ["direct-session"]
    assert "SynoToken" not in logout_body
    assert normalized_logout_headers["x-syno-token"] == "direct-token"


def test_synology_direct_auth_sends_optional_otp_only_during_login():
    opener = FakeOpener([
        {
            "success": True,
            "data": {
                "sid": "direct-session",
                "synotoken": "direct-token",
            },
        },
        {
            "success": True,
            "data": {
                "name": "alice",
            },
        },
        {
            "success": True,
            "data": {},
        },
    ])

    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials(
            username="alice",
            password="secret",
            otp_code="123456",
        ),
        opener=opener,
    )

    source.connect()

    assert opener.requests[0][1]["otp_code"] == ["123456"]
    assert "otp_code" not in opener.requests[1][1]

    source.close()


def test_direct_dialog_persists_username_but_not_password_or_otp():
    QApplication.instance() or QApplication([])

    captured = {}

    def provider_factory(base_url, authentication, **kwargs):
        captured["base_url"] = base_url
        captured["authentication"] = authentication
        captured["kwargs"] = kwargs
        return _DialogProvider(
            albums=[
                SourceCollection(
                    id="7",
                    name="Summer",
                    item_count=1,
                )
            ]
        )

    dialog = SynologySourceDialog(
        Translator("en"),
        provider_factory=provider_factory,
    )
    dialog.url_edit.setText("https://nas.example")
    dialog.username_edit.setText("alice")
    dialog.password_edit.setText("secret-password")
    dialog.otp_edit.setText("123456")

    dialog._connect()
    dialog._accept_source()

    credentials = captured["authentication"]
    assert isinstance(credentials, SynologyCredentials)
    assert credentials.username == "alice"
    assert credentials.password == "secret-password"
    assert credentials.otp_code == "123456"

    assert dialog.source.config == {
        "base_url": "https://nas.example",
        "api_path": "/webapi/entry.cgi",
        "username": "alice",
        "verify_tls": True,
    }

    serialized = dialog.source.to_json()
    assert "secret-password" not in serialized
    assert "123456" not in serialized

    dialog.provider.close()



def test_shared_album_metadata_does_not_switch_to_team_namespace():
    opener = FakeOpener([
        {
            "success": True,
            "data": {
                "sid": "direct-session",
                "synotoken": "direct-token",
            },
        },
        {
            "success": True,
            "data": {"name": "alice"},
        },
        {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 43,
                        "name": "Scootcoat",
                        "item_count": 1,
                    }
                ]
            },
        },
        {
            # Some DSM builds return the same album from a "shared"
            # category query and may decorate it with shared-space-like
            # metadata. It must still remain a SYNO.Foto album because
            # it was discovered through SYNO.Foto.Browse.Album.
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 43,
                        "name": "Scootcoat",
                        "item_count": 1,
                        "category": "shared_space",
                        "is_team": True,
                    }
                ]
            },
        },
        {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 219828,
                        "filename": "20250210_163439.jpg",
                        "type": "photo",
                        "additional": {
                            "thumbnail": {
                                "cache_key": "219828_key",
                            }
                        },
                    }
                ]
            },
        },
        {
            "success": True,
            "data": {},
        },
    ])

    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials(
            username="alice",
            password="secret",
        ),
        opener=opener,
    )

    collections = source.list_collections()
    assets = source.list_assets(collections[0].id)

    assert len(assets) == 1

    item_request = opener.requests[4][1]
    assert item_request["api"] == ["SYNO.Foto.Browse.Item"]
    assert item_request["album_id"] == ["43"]
    assert assets[0].metadata["_photoalbum_space"] == "personal"

    assert not any(
        request_body.get("api") == ["SYNO.FotoTeam.Browse.Item"]
        for _, request_body, _ in opener.requests
    )

    source.close()



def test_duplicate_shared_result_does_not_override_owned_album_context():
    opener = FakeOpener([
        {
            "success": True,
            "data": {
                "sid": "direct-session",
                "synotoken": "direct-token",
            },
        },
        {
            "success": True,
            "data": {"name": "alice"},
        },
        {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 43,
                        "name": "Scootcoat",
                        "item_count": 1,
                    }
                ]
            },
        },
        {
            # Simulate a DSM which ignores category=shared and returns
            # the owned album again with sharing-related metadata.
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 43,
                        "name": "Scootcoat",
                        "item_count": 1,
                        "category": "shared_space",
                        "sharing_id": "must-not-leak",
                        "passphrase": "must-not-leak",
                    }
                ]
            },
        },
        {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": 219828,
                        "filename": "20250210_163439.jpg",
                        "additional": {
                            "thumbnail": {
                                "cache_key": "219828_key",
                            }
                        },
                    }
                ]
            },
        },
        {
            "success": True,
            "data": {},
        },
    ])

    source = SynologyPhotosSource(
        "https://nas.example/",
        SynologyCredentials(
            username="alice",
            password="secret",
        ),
        opener=opener,
    )

    albums = source.list_collections()
    assert len(albums) == 1

    assert albums[0].metadata["_photoalbum_relation"] == "owned"
    assert "sharing_id" not in albums[0].metadata
    assert "passphrase" not in albums[0].metadata

    assets = source.list_assets("43")
    assert len(assets) == 1

    item_request = opener.requests[4][1]

    assert item_request["api"] == ["SYNO.Foto.Browse.Item"]
    assert item_request["album_id"] == ["43"]
    assert "passphrase" not in item_request

    source.close()
