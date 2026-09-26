from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from photoalbum.album.models import (
    CoverPosition,
)
from photoalbum.album.templates import (
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
    PageConstraints,
)
from photoalbum.template_engine.translations import (
    PackTranslator,
    load_pack_catalogs,
    replace_registered_pack_catalogs,
    translator_for_pack,
)
from photoalbum.template_engine.extensions import (
    collect_template_extensions,
    template_extension_registry,
)


if TYPE_CHECKING:
    from photoalbum.album.composition import TemplateLayoutRegistry
    from photoalbum.i18n import Translator
    from PySide6.QtWidgets import QWidget


class PackSettingsEditor(Protocol):
    def __call__(
        self,
        settings: dict[str, object],
        *,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> dict[str, object] | None:
        """Return updated pack settings, or None on cancellation."""
        ...

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
    modules: tuple[str, ...]  # Absolute import names declared by the manifest.
    documentation_paths: dict[str, Path] | None = None
    translation_catalogs: dict[str, dict[str, str]] | None = None
    settings_editor: str | None = None
    default_templates: dict[str, str] = field(default_factory=dict)

    def translator(self, base) -> PackTranslator:
        return PackTranslator(base, self.translation_catalogs or {})

    def documentation_path(
        self,
        language: str,
    ) -> Path | None:
        paths = self.documentation_paths or {}

        language = str(language or "en").lower()
        language = language.split("-", 1)[0]
        language = language.split("_", 1)[0]

        return (
            paths.get(language)
            or paths.get("en")
            or next(iter(paths.values()), None)
        )


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


def _constraints_from_data(value: object) -> PageConstraints:
    if not isinstance(value, dict):
        raise ValueError("Template page_constraints must be an object.")
    unknown = value.keys() - PageConstraints.__dataclass_fields__.keys()
    if unknown:
        raise ValueError(f"Unknown page constraints: {sorted(unknown)}")
    return PageConstraints(**value)


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

    if "targets" in value:
        raise ValueError("Template targets are obsolete; use optional page_constraints instead.")
    constraints = _constraints_from_data(value.get("page_constraints", {}))

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
        page_constraints=constraints,
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


def _documentation_paths(
    pack_path: Path,
    value: object,
) -> dict[str, Path]:
    """
    Resolve localized documentation supplied by a template pack.

    Documentation files must remain inside the pack directory.
    """
    if value is None:
        return {}

    if isinstance(value, str):
        entries = {"en": value}
    elif isinstance(value, dict):
        entries = value
    else:
        raise ValueError(
            "Template pack documentation must be a path "
            "or a language/path mapping"
        )

    pack_root = pack_path.resolve()
    result: dict[str, Path] = {}

    for language, raw_path in entries.items():
        language = str(language).strip().lower()
        relative = str(raw_path).strip()

        if not language or not relative:
            continue

        candidate = (pack_path / relative).resolve()

        try:
            candidate.relative_to(pack_root)
        except ValueError:
            raise ValueError(
                "Template pack documentation must remain inside "
                f"the pack directory: {relative!r}"
            ) from None

        # A localized file may deliberately be absent while a pack is
        # being translated. Runtime selection will fall back to EN.
        if candidate.is_file():
            result[language] = candidate

    return result


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
        documentation_paths=_documentation_paths(
            manifest_path.parent,
            data.get("documentation"),
        ),
        translation_catalogs=load_pack_catalogs(manifest_path.parent),
        settings_editor=_settings_editor_reference(data.get("settings_editor")),
        default_templates=_default_templates(data.get("default_templates", {}), definitions),
    )


def _default_templates(value, definitions) -> dict[str, str]:
    from photoalbum.template_engine.defaults import AlbumTemplateDefaults

    if not isinstance(value, dict):
        raise ValueError("default_templates must be an object.")
    definitions = {template.template_id: template for template in definitions}
    roles = {
        "front_cover": (TemplateKind.COVER, CoverPosition.FRONT),
        "inside_front_cover": (TemplateKind.COVER, CoverPosition.INSIDE_FRONT),
        "inside_back_cover": (TemplateKind.COVER, CoverPosition.INSIDE_BACK),
        "back_cover": (TemplateKind.COVER, CoverPosition.BACK),
        "photo_page": (TemplateKind.PHOTO_PAGE, None),
        "year_divider": (TemplateKind.YEAR_DIVIDER, None),
        "month_divider": (TemplateKind.MONTH_DIVIDER, None),
        "day_divider": (TemplateKind.DAY_DIVIDER, None),
    }
    for role, template_id in value.items():
        if role not in AlbumTemplateDefaults.__dataclass_fields__:
            raise ValueError(f"Unknown default template role: {role}")
        if not isinstance(template_id, str) or template_id not in definitions:
            raise ValueError(f"Default {role} must reference a template in its own pack.")
        kind, position = roles[role]
        template = definitions[template_id]
        if not template.supports(kind) or (position and not template.supports_cover_position(position)):
            raise ValueError(f"Default template {template_id!r} does not support {role}.")
    return dict(value)


def _settings_editor_reference(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        module, separator, attribute = value.partition(":")
        if separator and module and attribute.isidentifier() and all(
            part.isidentifier() for part in module.split(".")
        ):
            return value
    raise ValueError("settings_editor must be a 'module:callable' reference or null.")


def _builtin_templates_root() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
    )


def discover_template_packs(
    root: Path | None = None,
) -> tuple[TemplatePack, ...]:
    root = root or _builtin_templates_root()

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
        registry.pack_defaults[pack.pack_id] = dict(pack.default_templates)
        for template in pack.templates:
            registry.register(template)

    return DiscoveredTemplates(
        registry=registry,
        packs=packs,
    )


_active_packs: dict[str, TemplatePack] = {}


def _pack_catalogs_and_owners(
    packs: tuple[TemplatePack, ...],
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str]]:
    pack_catalogs: dict[str, dict[str, dict[str, str]]] = {}
    template_packs: dict[str, str] = {}

    for pack in packs:
        if pack.pack_id in pack_catalogs:
            raise ValueError(
                f"Duplicate active template pack ID: {pack.pack_id}"
            )
        pack_catalogs[pack.pack_id] = pack.translation_catalogs or {}

        for template in pack.templates:
            previous_pack_id = template_packs.get(template.template_id)
            if previous_pack_id is not None:
                raise ValueError(
                    f"Duplicate active template ID: {template.template_id} "
                    f"(packs {previous_pack_id} and {pack.pack_id})"
                )
            template_packs[template.template_id] = pack.pack_id

    return pack_catalogs, template_packs


def replace_active_template_packs(
    packs: tuple[TemplatePack, ...],
) -> None:
    """Activate pack metadata/catalogs and discard previous executable extensions.

    Use register_discovered_template_extensions to also load executable behavior.
    Layouts remain local to each composer's registry.
    """
    global _active_packs
    pack_catalogs, template_packs = _pack_catalogs_and_owners(packs)
    replace_registered_pack_catalogs(pack_catalogs, template_packs)
    _active_packs = {pack.pack_id: pack for pack in packs}
    template_extension_registry.replace({})


def register_discovered_template_extensions(
    packs: tuple[TemplatePack, ...] | None = None,
) -> tuple[TemplatePack, ...]:
    if packs is None:
        packs = discover_template_packs()

    _pack_catalogs_and_owners(packs)
    extensions = {}
    for pack in packs:
        with collect_template_extensions() as collected:
            for module_name in pack.modules:
                module = import_module(module_name)
                register = getattr(module, "register", None)
                if not callable(register):
                    raise ValueError(
                        "Template module has no register() function: "
                        f"{module.__name__}"
                    )
                register()
            undeclared = collected.keys() - {t.template_id for t in pack.templates}
            if undeclared:
                raise ValueError(
                    f"Pack {pack.pack_id!r} registered undeclared template IDs: "
                    f"{sorted(undeclared)}"
                )
            extensions.update(collected)

    replace_active_template_packs(packs)
    template_extension_registry.replace(extensions)

    return packs


def create_template_registry() -> TemplateRegistry:
    return discover_templates().registry


def register_discovered_layouts(
    registry: TemplateLayoutRegistry,
    packs: tuple[TemplatePack, ...] | None = None,
) -> None:
    """Load pack-owned composition without initializing settings widgets."""
    if packs is None:
        packs = discover_template_packs()
    _pack_catalogs_and_owners(packs)
    for pack in packs:
        for module_name in pack.modules:
            module = import_module(module_name)
            register = getattr(module, "register_layouts", None)
            if register is not None:
                if not callable(register):
                    raise ValueError(
                        f"Template module has no callable register_layouts(): {module_name}"
                    )
                register(registry)
        for template in pack.templates:
            if TemplateKind.PHOTO_PAGE in template.allowed_kinds:
                # Fail early with the missing template ID, before rendering.
                registry.get(template.template_id)


def pack_settings_editor(pack_id: str) -> PackSettingsEditor | None:
    """Return the optional pack-owned settings dialog callback."""
    pack = _active_packs.get(pack_id)
    if pack is None or pack.settings_editor is None:
        return None
    module_name, attribute = pack.settings_editor.split(":")
    module = import_module(module_name)
    editor = getattr(module, attribute, None)
    if not callable(editor):
        raise ValueError(f"Pack settings editor is not callable: {pack.settings_editor}")

    def localized_editor(settings, *, translator, parent=None):
        return editor(
            settings,
            translator=translator_for_pack(pack_id, translator),
            parent=parent,
        )

    return localized_editor
