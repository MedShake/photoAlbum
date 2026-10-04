from __future__ import annotations

from dataclasses import dataclass, field
import json
from collections.abc import Mapping
import re

from .base import SourceCapabilities


_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "credential",
    "secret",
    "token",
)
_SENSITIVE_KEYS = {
    "apikey",
    "did",
    "privatekey",
    "sessionid",
    "sid",
    "otp",
    "otpcode",
}


def _reject_sensitive_config(value: object, path: str = "config") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            normalized = re.sub(r"[^a-z0-9]", "", key_text.casefold())
            if (
                normalized in _SENSITIVE_KEYS
                or any(part in normalized for part in _SENSITIVE_KEY_PARTS)
                or normalized.startswith("otp")
            ):
                raise ValueError(
                    f"Sensitive project source configuration key: "
                    f"{path}.{key_text}"
                )
            _reject_sensitive_config(nested, f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_sensitive_config(nested, f"{path}[{index}]")


@dataclass(frozen=True)
class ProjectSource:
    """Persistable source selection. Secrets must never be put in config."""

    id: str
    kind: str
    name: str
    collection_id: str
    collection_name: str
    config: dict[str, object] = field(default_factory=dict)
    provider_label: str | None = None
    capabilities: SourceCapabilities | None = None

    def to_json(self) -> str:
        _reject_sensitive_config(self.config)
        return json.dumps(
            {
                "schema_version": 2,
                "id": self.id,
                "kind": self.kind,
                "name": self.name,
                "collection_id": self.collection_id,
                "collection_name": self.collection_name,
                "config": self.config,
                "provider_label": self.provider_label,
                "capabilities": (
                    {
                        "date": sorted(self.capabilities.date_candidates),
                        "gps": sorted(self.capabilities.gps_candidates),
                        "location": sorted(self.capabilities.location_candidates),
                        "caption": sorted(self.capabilities.caption_candidates),
                        "can_fetch_original": self.capabilities.can_fetch_original,
                    }
                    if self.capabilities is not None
                    else None
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> "ProjectSource":
        data = json.loads(value)
        if data.get("schema_version") not in (1, 2):
            raise ValueError("Unsupported project source schema.")
        config = dict(data.get("config") or {})
        _reject_sensitive_config(config)
        raw_capabilities = data.get("capabilities")
        capabilities = None
        if isinstance(raw_capabilities, Mapping):
            capabilities = SourceCapabilities(
                date_candidates=frozenset(raw_capabilities.get("date") or ()),
                gps_candidates=frozenset(raw_capabilities.get("gps") or ()),
                location_candidates=frozenset(
                    raw_capabilities.get("location") or ()
                ),
                caption_candidates=frozenset(
                    raw_capabilities.get("caption") or ()
                ),
                can_fetch_original=bool(
                    raw_capabilities.get("can_fetch_original", False)
                ),
            )
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            name=str(data["name"]),
            collection_id=str(data["collection_id"]),
            collection_name=str(data["collection_name"]),
            config=config,
            provider_label=(
                str(data["provider_label"])
                if data.get("provider_label")
                else None
            ),
            capabilities=capabilities,
        )
