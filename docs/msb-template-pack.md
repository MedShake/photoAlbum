# MSB template pack

**MSB** is the original template pack bundled with Photo Album.

It contains the historical templates used for covers, special pages,
year and month dividers, and ordinary photo pages.

The pack is identified by `msb`. Its catalog is declared in:

    src/photoalbum/templates/msb/manifest.json

The manifest is the source of truth for template availability,
supported page kinds, cover positions, optional physical page bounds,
and photo capacities.

## Physical page compatibility

Most MSB templates declare no geometric bounds. The classic month divider requires
at least 130 × 145 mm; the calendar index requires at least 110 × 260 mm. The host supplies physical
page dimensions, including the chosen orientation. Named formats do not restrict
template compatibility. Cover-position and page-kind restrictions still apply.

An album can mix templates from MSB with templates supplied by other
installed packs.

## Template catalog

MSB currently contains the following templates.

| Template ID | Name | Uses |
| --- | --- | --- |
| `year-photo-scatter` | Year photo scatter | Cover, special page |
| `geographic-word-cloud` | Geographic word cloud | Cover, special page |
| `calendar-index` | Annual calendar | Cover, special page, year divider |
| `year-divider-classic` | Simple year divider | Year divider |
| `month-divider-classic` | Month divider with city list | Month divider |
| `month-divider-simple` | Simple month divider | Month divider |
| `photo-page-1` | One photo | Photo page |
| `photo-page-2` | Two photos | Photo page |
| `photo-page-3` | Three photos | Photo page |
| `photo-page-4` | Four photos | Photo page |
| `dedication` | Dedication | Special page, inside back cover |
| `blank` | Blank page | Special page |

The user-visible names are translated by Photo Album. For example,
the French catalog uses names such as *Pêle-mêle annuel*,
*Nuage géographique*, *Calendrier annuel*, *Dédicace*, and
*Page blanche*.

## Covers

Three general MSB templates can be used at all four cover positions:

- `year-photo-scatter`;
- `geographic-word-cloud`;
- `calendar-index`.

Their allowed positions are:

- front cover;
- inside front cover;
- inside back cover;
- back cover.

`dedication` has a more restricted role as a cover template: it is
available only for the inside back cover.

The same templates can also be used as special pages where declared
by the manifest.

## Year photo scatter

`year-photo-scatter` creates a photographic composition from project
photos associated with a year.

The template owns its composition, preview, settings, and rendering
code. Its preview backend filters the supplied project photos and
ignores photos without a capture date. Duplicate paths are reduced
to one photo before the effective photo set is built.

The template can be used as:

- a cover;
- a special page.

Its settings are local to the page instance, while common visual
choices can inherit from the MSB pack theme.

## Geographic word cloud

`geographic-word-cloud` creates a geographic composition from the
location information associated with the project's photos.

The settings allow the relevant year to be selected and provide a
12-month color palette.

By default, the template inherits its monthly colors from the MSB
theme. A page can override that palette locally. The local override
can subsequently be removed to restore the pack theme.

The template can be used as:

- a cover;
- a special page.

## Annual calendar

`calendar-index` renders an annual calendar/index from album data.

It can be used as:

- a cover;
- a special page;
- a year divider.

The settings include the displayed year and whether the title is
shown.

When the template is used as a year divider, the year is determined
by the divider context rather than freely selected by the user.

The renderer uses the album structure to associate calendar months
with the corresponding album page numbers.

## Simple year divider

`year-divider-classic` is the classic MSB year separator.

Its page-specific presentation settings include:

- title font family;
- title font size;
- title color.

The font defaults can inherit from the shared MSB theme.

The settings editor follows the standard two-column convention:
page settings on the left and live preview on the right.

## Month divider with city list

`month-divider-classic` is the detailed MSB month separator.

It is intended to identify a month while also presenting geographic
information associated with that period, including its city list.

Its appearance participates in the common MSB theme and it has its
own page-level settings.

## Simple month divider

`month-divider-simple` is the minimal MSB month separator.

Its page-level typography includes:

- title font family;
- title font size.

The font family defaults to the shared MSB theme unless overridden
for the page.

Use this template when the month heading itself is sufficient and
the city list of the classic divider is not wanted.

## Photo pages

MSB supplies four ordinary photo-page layouts:

- `photo-page-1` — one photo;
- `photo-page-2` — two photos;
- `photo-page-3` — three photos;
- `photo-page-4` — four photos.

Their declared capacities are respectively 1, 2, 3, and 4 photos.

All four templates share the `photo_page` implementation and a common
renderer/settings editor, while each template ID has its own physical
layout.

### Captions

MSB photo pages support three sources of caption information:

- the user caption;
- capture date/time;
- location.

Each component can be enabled or disabled.

The default ordering is:

1. user caption;
2. capture date/time;
3. line break;
4. location.

Visible elements on the same line are separated typographically by
an em dash.

The caption system also supports page-level presentation settings
such as font and color.

MSB photo layouts reserve caption space as part of physical page
composition rather than painting captions over the photographs.
The built-in layouts support up to three caption lines per photo.

## Dedication

`dedication` provides a dedicated text page.

It is declared both as a special page and as a cover template, but
its cover use is deliberately restricted to the inside back cover.

This makes it suitable for an end-of-album dedication without making
it appear among unrelated front-cover choices.

## Blank page

`blank` is the simplest MSB template.

It creates an intentionally empty special page and has no photo
capacity.

Besides being useful in an album layout, it is also a useful reference
implementation for the minimum template rendering/settings contract.

## Shared MSB theme

MSB has pack-level settings shared by its templates.

The theme currently owns:

- a default font family;
- a palette containing one color for each month.

Page-specific settings remain stored on the page instance. Shared
theme settings remain in the album's template-pack settings under the
`msb` pack key.

This distinction allows a page to inherit the common MSB appearance
while retaining local overrides where a template supports them.

For example, the geographic word cloud can inherit the monthly palette
or store its own local palette.

Template settings editors can request the MSB theme editor through the
common `edit_theme_requested` mechanism.

## Settings UI and previews

MSB settings editors use the common template-settings infrastructure.

The convention is a two-column layout:

- page/template controls on the left;
- live preview on the right.

Changing a setting updates the page instance and refreshes the preview.

The same executable template behavior is used by the application
preview and final rendering paths. Templates must therefore remain
renderable without depending on asynchronous preview-only services.

## Implementation structure

The MSB package contains shared infrastructure in addition to the
individual template modules.

Important shared modules include:

- `settings_base.py` — common MSB settings-editor behavior;
- `theme.py` — shared theme representation and palette handling;
- `theme_dialog.py` — editor for pack-level theme settings;
- `divider_style.py` — shared divider typography helpers;
- `photo_page/layout.py` — physical layouts for the four photo pages;
- `photo_page/caption_layout.py` — caption-space calculation;
- `photo_page/caption_style.py` — caption visibility, ordering, and
  presentation.

Each executable template module exposes `register()` and registers a
`PageTemplateExtension`.

Photo-page templates additionally register their physical composition
layouts. Because the four photo-page IDs share one module, that module
registers all four layouts in a single registration pass.

## Rendering contract

Template widget renderers are used by both GUI preview and PDF export.

Depending on the template type, rendering receives information such
as:

- the page instance;
- project/effective photos;
- physical page dimensions;
- target pixel rectangle;
- translator;
- album pages;
- thumbnail cache;
- composed photo layout;
- MSB pack settings.

PDF rendering cannot rely on an asynchronous GUI preview service, so
MSB renderers must also be able to paint immediately.

## Adding or changing MSB templates

The manifest is the catalog authority. Adding a template generally
requires:

1. declaring it in `manifest.json`;
2. providing an importable template module;
3. registering its executable extension;
4. providing a layout registration when it is a `photo_page`;
5. adding translated user-visible names;
6. covering discovery, settings, preview, composition, and PDF export
   with tests.

For the general template-pack architecture, see:

- `docs/template-packs.md`;
- `docs/gui-architecture.md`.

For a smaller independent pack example, see:

- `docs/simplex-template-pack.md`.

### Minimum page dimensions

The classic month divider requires width ≥ 130 mm and height ≥ 145 mm.
Its 32 pt month/year heading needs about 105.5 mm for the longest default
French/English label, plus two 10 mm margins. The city area begins at 40 mm
and occupies 65% of page height: 145 mm retains a bottom margin of at least
10 mm (below 114.3 mm the rectangle exceeds the page).

The calendar index requires width ≥ 110 mm and height ≥ 260 mm. It uses two
columns and six rows, a 28 mm title band, 10 mm margins, 8 mm column spacing,
and fixed 4 mm day cells. Each month can need 33 mm for its heading, weekday
header and six weeks; 260 mm provides over 2 mm between these blocks. The
110 mm width keeps weekday labels and typical month/page headings readable.
These bounds cover default typography and ordinary content; unusually long
city lists or custom large fonts may still need a larger page. No bounds were
added to the photo scatter template.
