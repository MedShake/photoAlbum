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
    README.md               # optional
```

The directory name must match the manifest's `id` and be an importable Python
package name. Template IDs must be unique across all packs; prefixing them with
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
    "module": "photo",
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

## Registering behavior

Each module declared in the manifest exposes `register()`. Qt editor imports can
remain inside this function: discovering the catalog and layouts must not create
widgets.

```python
# my_pack/photo/__init__.py
from photoalbum.template_engine import (
    PageTemplateExtension, register_template_extension,
)


def register():
    from .widget_renderer import PhotoRenderer
    from .settings import PhotoSettingsWidget

    register_template_extension(PageTemplateExtension(
        template_id="my-pack-photo",
        widget_renderer=PhotoRenderer(),
        settings_editor_type=PhotoSettingsWidget,  # optional
    ))


def register_layouts(registry):
    from photoalbum.album.composition import NormalizedRect, PhotoTemplateLayout

    registry.register("my-pack-photo", PhotoTemplateLayout(
        cells_factory=lambda width_mm, height_mm: (
            NormalizedRect(x=0.1, y=0.1, width=0.8, height=0.8),
        ),
    ))
```

`register_layouts(registry)` is required for `photo_page` templates. It receives
a fresh registry when the composer is created. Other page types do not need it.
A module shared by several templates is processed only once per registration
pass, so it must register all their IDs. A missing layout produces an error
identifying the template concerned.

`PhotoTemplateLayout` composes photos and captions, with parameters for the gap
between image and caption, the maximum number of caption lines, text metrics,
and page numbering. A pack can also provide its own object implementing
`TemplateLayout.compose()`. Shared caption space across a two-page spread is
supported for `PhotoTemplateLayout`.

## Rendering and settings

The same `widget_renderer.paint()` handles previews and PDF output. Its arguments
include `painter`, `instance`, `photos`, `target_rect`, `width`, `height`,
`translator`, `font_pixel_size`, `page_width_mm`, `page_height_mm`, `album_pages`,
and `thumbnail_cache`. Photo pages also receive `composition` and `pixel_rect`.
Accepting `**kwargs` allows a template to ignore arguments it does not need.
Explicitly declare `template_pack_settings=None` to receive pack settings in
all rendering paths, and `project_photos=None` if needed.

PDF export passes `render_service=None`: the renderer must be able to draw
immediately without an asynchronous preview service. MSB includes simple examples
(`blank`) and more elaborate ones (`photo_page`, `year_photo_scatter`).

Local settings are stored in `PageInstance.settings`. Shared settings live in
`AlbumStructureSettings.template_pack_settings`, under a key matching the pack
ID. Their format is owned by the pack.

To provide a shared settings dialog, expose this hook in the pack's `__init__.py`:

```python
def edit_settings(settings, *, translator, parent=None):
    # Open the pack's settings dialog.
    # Return a new complete dictionary, preserving settings for other packs.
    # Return None on cancellation; do not modify settings in place.
    ...
```

A template editor can emit the Qt signal `edit_theme_requested`. The GUI then
looks up the selected template's pack and calls this hook. Without the hook,
no pack settings dialog is opened.

## Packaging and verification

Manifests, `README.md`, `screenshots/*`, and `assets/` (recursively) are included
automatically in Python distributions. PyInstaller already collects submodules
and data from all packs. Packs are added to the source tree: an application that
has already been distributed must be rebuilt to include a new pack.

Before distributing a pack, verify discovery, composition, settings, preview,
and PDF export. `tests/test_template_pack_integration.py` exercises a temporary
pack independent of MSB, from discovery through export.
