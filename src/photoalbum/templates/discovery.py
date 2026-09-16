from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import json
from pathlib import Path

from photoalbum.album.models import (
    CoverPosition,
    PAGE_FORMATS,
)
from photoalbum.album.settings import PageOrientation
from photoalbum.album.templates import (
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
    TemplateTarget,
)


MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class TemplatePack:
    pack_id: str
    name: str
    version: str
    path: Path
    description: str | None
    authors: tuple[str, ...]
    templates: tuple[TemplateDefinition, ...]
    modules: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveredTemplates:
    registry: TemplateRegistry
    packs: tuple[TemplatePack, ...]


def _manifest_paths(
    root: Path,
) -> list[Path]:
    return sorted(
        path / MANIFEST_FILENAME
        for path in root.iterdir()
        if (
            path.is_dir()
            and not path.name.startswith("_")
            and (path / MANIFEST_FILENAME).is_file()
        )
    )


def _target_from_data(
    value: object,
) -> TemplateTarget:
    if not isinstance(value, dict):
        raise ValueError("Template target must be an object.")

    format_id = str(value.get("format", ""))
    orientation_value = str(
        value.get("orientation", "")
    )

    if format_id not in PAGE_FORMATS:
        raise ValueError(
            f"Unknown page format in template manifest: "
            f"{format_id!r}"
        )

    try:
        orientation = PageOrientation(
            orientation_value
        )
    except ValueError:
        raise ValueError(
            "Unknown page orientation in template manifest: "
            f"{orientation_value!r}"
        ) from None

    return TemplateTarget(
        format_id=format_id,
        orientation=orientation,
    )


def _template_from_data(
    *,
    pack_id: str,
    pack_name: str,
    value: object,
) -> tuple[TemplateDefinition, str]:
    if not isinstance(value, dict):
        raise ValueError(
            "Template manifest entry must be an object."
        )

    template_id = str(value.get("id", "")).strip()
    name = str(value.get("name", "")).strip()
    module = str(value.get("module", "")).strip()

    if not template_id:
        raise ValueError("Template manifest ID is required.")

    if not name:
        raise ValueError(
            f"Template {template_id!r} has no name."
        )

    if not module:
        raise ValueError(
            f"Template {template_id!r} has no module."
        )

    try:
        kinds = frozenset(
            TemplateKind(str(item))
            for item in value.get("kinds", [])
        )
    except ValueError as exc:
        raise ValueError(
            f"Template {template_id!r} has an unknown kind."
        ) from exc

    targets = frozenset(
        _target_from_data(item)
        for item in value.get("targets", [])
    )

    try:
        cover_positions = frozenset(
            CoverPosition(str(item))
            for item in value.get(
                "cover_positions",
                [],
            )
        )
    except ValueError as exc:
        raise ValueError(
            f"Template {template_id!r} has an unknown "
            "cover position."
        ) from exc

    localized_names = value.get(
        "localized_names",
        {},
    )
    localized_descriptions = value.get(
        "localized_descriptions",
        {},
    )

    if not isinstance(localized_names, dict):
        raise ValueError(
            f"Template {template_id!r}: "
            "localized_names must be an object."
        )

    if not isinstance(localized_descriptions, dict):
        raise ValueError(
            f"Template {template_id!r}: "
            "localized_descriptions must be an object."
        )

    definition = TemplateDefinition(
        template_id=template_id,
        name=name,
        allowed_kinds=kinds,
        photo_capacity=int(
            value.get("photo_capacity", 0)
        ),
        pack_id=pack_id,
        pack_name=pack_name,
        supported_targets=targets,
        cover_positions=cover_positions,
        localized_names={
            str(key): str(item)
            for key, item in localized_names.items()
        },
        localized_descriptions={
            str(key): str(item)
            for key, item
            in localized_descriptions.items()
        },
    )

    return definition, module


def load_template_pack(
    manifest_path: Path,
) -> TemplatePack:
    data = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid template manifest: {manifest_path}"
        )

    if data.get("schema_version") != 1:
        raise ValueError(
            f"Unsupported template manifest schema in "
            f"{manifest_path}"
        )

    pack_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    version = str(data.get("version", "")).strip()

    if not pack_id:
        raise ValueError(
            f"Template pack has no ID: {manifest_path}"
        )

    if not name:
        raise ValueError(
            f"Template pack has no name: {manifest_path}"
        )

    if manifest_path.parent.name != pack_id:
        raise ValueError(
            "Template pack directory must match its ID: "
            f"{manifest_path.parent.name!r} != {pack_id!r}"
        )

    raw_templates = data.get("templates", [])

    if not isinstance(raw_templates, list):
        raise ValueError(
            f"templates must be a list in {manifest_path}"
        )

    definitions = []
    modules = []

    for raw_template in raw_templates:
        definition, module = _template_from_data(
            pack_id=pack_id,
            pack_name=name,
            value=raw_template,
        )
        definitions.append(definition)
        modules.append(module)

    raw_authors = data.get("authors", [])
    authors = []

    if isinstance(raw_authors, list):
        for author in raw_authors:
            if isinstance(author, dict):
                author_name = str(
                    author.get("name", "")
                ).strip()
            else:
                author_name = str(author).strip()

            if author_name:
                authors.append(author_name)

    return TemplatePack(
        pack_id=pack_id,
        name=name,
        version=version,
        path=manifest_path.parent,
        description=(
            str(data["description"])
            if data.get("description") is not None
            else None
        ),
        authors=tuple(authors),
        templates=tuple(definitions),
        modules=tuple(dict.fromkeys(modules)),
    )


def discover_template_packs(
    root: Path | None = None,
) -> tuple[TemplatePack, ...]:
    root = root or Path(__file__).resolve().parent

    return tuple(
        load_template_pack(path)
        for path in _manifest_paths(root)
    )


def discover_templates(
    root: Path | None = None,
) -> DiscoveredTemplates:
    packs = discover_template_packs(root)
    registry = TemplateRegistry()

    seen_pack_ids: set[str] = set()

    for pack in packs:
        if pack.pack_id in seen_pack_ids:
            raise ValueError(
                f"Duplicate template pack ID: {pack.pack_id}"
            )

        seen_pack_ids.add(pack.pack_id)

        for template in pack.templates:
            registry.register(template)

    return DiscoveredTemplates(
        registry=registry,
        packs=packs,
    )


def register_discovered_template_extensions(
    packs: tuple[TemplatePack, ...] | None = None,
) -> tuple[TemplatePack, ...]:
    packs = packs or discover_template_packs()

    for pack in packs:
        for module_name in pack.modules:
            module = import_module(
                f"photoalbum.templates."
                f"{pack.pack_id}.{module_name}"
            )

            register = getattr(module, "register", None)

            if not callable(register):
                raise ValueError(
                    "Template module has no register() function: "
                    f"{module.__name__}"
                )

            register()

    return packs


def create_template_registry() -> TemplateRegistry:
    return discover_templates().registry
