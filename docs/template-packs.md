# Adding a template pack

MSB remains the bundled pack and the default selection. Additional packs can be
added under `src/photoalbum/templates/` without changing the engine, GUI, or
packaging configuration. An album can mix templates from multiple packs.
Templates are executable Python modules, rather than HTML or Jinja files.

## Structure

```text
src/photoalbum/templates/my_pack/
    __init__.py
    manifest.json
    photo/
        __init__.py
        layout.py
        widget_renderer.py
        settings.py
    assets/                 # optional; may contain subdirectories
    screenshots/            # optional
    i18n/en.json            # optional pack catalog
    docs/help.html          # optional pack documentation
    README.md               # optional
```

The directory name must match the manifest's `id`. Python modules referenced
by the manifest must be importable; the ID itself is not used to construct imports. Template IDs must be unique across all packs; prefixing them with
the pack name avoids collisions.

```json
{
  "schema_version": 1,
  "id": "my_pack",
  "name": "My pack",
  "version": "1.0",
  "templates": [{
    "id": "my-pack-photo",
    "name": "One photo",
    "localized_names": {"fr": "Une photo", "en": "One photo"},
    "module": "photoalbum.templates.my_pack.photo",
    "kinds": ["photo_page"],
    "photo_capacity": 1
  }]
}
```

A pack can provide only some page types, with MSB providing the others. Available
types are `photo_page`, `cover`, `special_page`, `month_divider`, and
`year_divider`. For covers, specify `cover_positions`: `front`, `inside_front`,
`inside_back`, and `back`. See the MSB manifest for a complete example.

## Physical page compatibility

The host owns named paper formats and orientation. It resolves these choices
into width and height in millimetres before checking a template or rendering it.
Templates do not declare format names or orientation whitelists. The former
`targets` field is rejected; remove it when migrating a pack.

A template can optionally declare `page_constraints` with independently optional
`min_width_mm`, `max_width_mm`, `min_height_mm`, and `max_height_mm` fields.
For example, a hypothetical template with a measured width limitation could use:

```json
"page_constraints": {"min_width_mm": 180, "max_width_mm": 320}
```

Bounds are inclusive, positive finite numbers; a minimum must not exceed its
corresponding maximum. Omitted or null bounds impose no restriction. Omitting
`page_constraints` entirely leaves the template geometrically unrestricted.
There is no aspect-ratio constraint. Most bundled templates omit bounds; add a restriction only after a real
limitation has been established. See the MSB pack documentation for its measured minima.

`TemplateDefinition.is_compatible_with_page(width_mm, height_mm)` delegates to
`PageConstraints.accepts`, the single geometric decision point. The registry
provides `list_for_page` and `album_page_available` using this same check.
Kinds and cover positions remain independent restrictions.

`photo-album-cli templates` lists one row per discovered template, including the
four bounds in millimetres and album usage. `-` denotes an absent bound or a
non-applicable cover position. `--format json` exposes the same collected data,
using null for absent bounds and non-applicable positions.

## Public authoring API

Pack code imports host primitives from `photoalbum.template_engine.api`:

```python
from photoalbum.template_engine.api import (
    PageInstance, PageTemplateExtension, register_template_extension,
    NormalizedRect, PageComposition, PhotoSlotComposition, TemplateLayout,
    PageComposer, PreviewJob, TemplatePreviewBackend, PageTemplateSettingsWidget,
)
```

This entry point exposes the generic instance/page models, layout and composition
primitives, preview backend contract, and settings editor base class. Authors do
not need internal modules such as `album.composition`, `preview_backend`, or
`gui.template_settings.base`. The exports refer to the actual host types; there
are no compatibility wrappers and no pack-specific implementations in this API.
Importing it does not activate packs or construct services/widgets.

Editors consume the host-provided `self._render_service`. The application normally
injects its shared service. When an editor is created standalone without a service,
the host's `PageTemplateSettingsWidget` provides one owned by the widget. A pack
must not construct `PreviewRenderService` itself. Workers implementing a pack's
preview calculation still belong in that pack.

## Registering behavior

The existing `module` field is an absolute, importable Python module name.
It is never inferred from the pack ID or its directory. External installed
packages can be referenced too. No Python code is imported during discovery.

Each module declared in the manifest exposes `register()`. Qt editor imports can
remain inside this function: discovering the catalog and layouts must not create
widgets.

```python
# my_pack/photo/__init__.py
from photoalbum.template_engine.api import (
    PageTemplateExtension, register_template_extension,
)


def validate(settings):
    if not isinstance(settings.get("density"), int):
        raise ValueError("density must be an integer")


def register():
    from .widget_renderer import PhotoRenderer
    from .settings import PhotoSettingsWidget

    register_template_extension(PageTemplateExtension(
        template_id="my-pack-photo",
        widget_renderer=PhotoRenderer(),
        settings_editor_type=PhotoSettingsWidget,  # optional
        settings_defaults=lambda: {"density": 17},  # optional; otherwise {}
        validate_settings=validate,  # optional callable(settings), raises ValueError
        photo_scope="page",  # or "album" to use all project photos
    ))


def register_layouts(registry):
    from .layout import PhotoLayout
    registry.register("my-pack-photo", PhotoLayout())
```

`register_layouts(registry)` is required for templates declaring photo capacity.
Other templates can also supply layouts. Each layout implements
`compose(page, instance, page_numbers, *, page_width_mm, page_height_mm,
reserved_caption_lines=None)` and returns a `PageComposition`. `instance.settings`
is opaque to the engine. The pack owns all its geometry, content preparation and
caption rules. Generic rectangles, slots and page-number composition are available
from the public authoring API; there is no built-in pack-specific layout there.

A layout can optionally implement `required_caption_lines(page, instance, *,
page_width_mm, page_height_mm)` and `reserve_caption_lines(required)`. The composer
can then share measurements across a spread and report overflow; the pack decides
how text is measured and how much space is reserved. Other layouts need neither.

A module shared by several templates is processed only once per registration
pass, so it must register all their IDs. A missing required layout produces an
error identifying the template. A standalone occurrence uses
`PageComposer.compose_instance(instance, photos, ...)`, including outside normal
pagination. This allows an optional layout to work on covers too.

## Rendering and settings

`PageRenderer.paint_template()` is the single dispatch point for all template
renderers: settings previews, paginated pages, covers and PDF. There is no dispatch
branch based on a template ID or album role. The `paint()` wrapper handles page
numbers and the application's fallback display for pages without a renderer.

Every `widget_renderer.paint()` receives the same keyword context:

- `painter`, `target_rect`, `width`, `height`, physical dimensions,
  `font_pixel_size`, `pixel_rect`;
- `instance`, its opaque `settings`, `template_pack_settings`;
- `photos` (page or album according to `photo_scope`), `project_photos`,
  `album_pages`, `composition` and `thumbnail_cache`;
- the **pack translator**, `render_service`, `set_waiting_key`, `show_empty_slots`.

Declare the arguments used and accept `**kwargs` for the others. No signature
inspection or historical renderer adapter is used. PDF sets `render_service=None`;
the renderer must be able to render synchronously too. An optional
`TemplatePreviewBackend` supplies expensive asynchronous jobs through `PreviewJob`.
Its worker and business logic belong in the pack, while the host schedules work
and caches results.

`create_template_instance(template_id)` calls the optional pack defaults factory,
copies its result, and invokes optional validation. Album validation invokes the
same validation callback before composition/export. Loading settings preserves
saved values; it never replaces them with fresh defaults. Renderers can also
interpret omitted options locally, as the built-in packs do.

Local settings are JSON-compatible dictionaries in `PageInstance.settings`.
Shared settings are in `AlbumStructureSettings.template_pack_settings`, keyed by
pack ID. Their meaning, validation and editors belong entirely to the pack.

To provide a shared settings dialog, declare its entry point in the manifest:

```json
"settings_editor": "photoalbum.templates.my_pack.options:edit_settings"
```

The module and callable name are chosen by the pack. Omit the field or use
`null` when there is no pack editor. The callback has this signature:

```python
def edit_settings(settings, *, translator, parent=None):
    # Open the pack's settings dialog.
    # Return a new complete dictionary, preserving settings for other packs.
    # Return None on cancellation; do not modify settings in place.
    ...
```

A template editor can emit the Qt signal `edit_theme_requested`. The GUI then
looks up the selected template's pack and calls this hook. Without the declaration,
no pack settings dialog is opened.

## Discovery and activation

`discover_template_packs()` and `discover_templates()` are read-only: local
catalog inspection never replaces active translations, editors or extensions.
`register_discovered_template_extensions(packs)` activates the supplied set
(or the discovered built-in set if omitted), replacing translations, editor
metadata and executable extensions. Removed packs leave no registered behavior.
Registration is collected before publication, so a missing module, missing
`register()`, duplicate extension or undeclared template ID leaves the previous
active set intact. Python import side effects are not rolled back.

`replace_active_template_packs(packs)` activates metadata/catalogs only and clears
previous extensions; use the registration function when executable behavior is
needed. An editor is imported lazily when requested. An invalid declared editor
raises an error; it is not treated as an absent editor.

Layouts use the same declared modules but remain local to each composer's
registry. Existing composers retain their layouts; create a new composer after
changing the installed set. Discovery, layout loading and metadata activation
do not import an editor merely because it is declared in a manifest.

The application declares only `DEFAULT_TEMPLATE_PACK = "msb"`. The selected
pack's optional `default_templates` manifest object maps album roles to its own
IDs: `front_cover`, `inside_front_cover`, `inside_back_cover`, `back_cover`,
`photo_page`, `year_divider`, `month_divider`. These seven roles are required for
the default pack and validated against each template's supported uses. They are
not required for other packs. A missing default pack produces a clear error when
creating the album settings UI, never an import failure or an order-based choice.
Incompatible defaults still leave the first available GUI choice selected.

## Translations and resources

Put catalogs in `i18n/<language>.json`. Fallback is the selected pack language,
then English in that pack, then the application catalog, then the key. Renderers,
editors, labels and asynchronous previews use this routing, including PDF covers.
Packs never use another pack's catalogs. Global catalogs contain application text.

Declare `documentation` as a relative path or a language/path mapping. The help
UI discovers it generically; missing localized files fall back to English.
Assets live under the pack directory and can be resolved relative to the pack's
own Python modules. No central resource list or central documentation change is
needed to make a new pack work.

## Packaging and verification

Manifests, `README.md`, `docs/*`, `i18n/*.json`, `screenshots/*`, and `assets/` (recursively) are included
automatically in Python distributions. PyInstaller already collects submodules
and data from all packs. Packs are added to the source tree: an application that
has already been distributed must be rebuilt to include a new pack.

Before distributing a pack, verify discovery, composition, settings, preview,
and PDF export. `tests/fixtures/template_packs/testpack/` is an independent
example with opaque settings, editors, renderer, layout, async preview, catalogs,
asset and documentation. The lifecycle test copies only its directory into a
source tree, exercises the GUI, persistence and export, and then physically
removes packs. The distribution test also adds it before building the sdist and
wheel, installs the wheel, and runs the same lifecycle outside the checkout.
