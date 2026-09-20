# GUI architecture

`MainWindow` coordinates the open project, workflow tabs, album construction,
and view synchronization. Changes to places and captions are saved immediately;
the album is rebuilt when the user leaves that tab, or before exporting a PDF.

The following components own their state and responsibilities:

- `PhotoSourcesWidget`: source folder controls, table models, sorting, selection,
  logging, and hover previews. User actions are emitted as signals; this widget
  has no knowledge of `MainWindow`.
- `ScanController`: scan startup and cancellation, the worker thread, progress,
  and reporting in the source widget. It notifies the window when photos become
  available or the scan state changes.
- `PhotoEditor`: date and GPS dialogs, persistence through `ProjectService`,
  geocoding, and opening images. It emits errors, log messages, and refresh
  requests.
- `PdfExportWidget`: PDF options, validation, background export, and progress.
  It explicitly receives the project service and callbacks for reading settings,
  obtaining the album, and preparing the export.

Components receive their dependencies through their constructors. Their Qt
parent manages their lifetime and dialog placement; it is never used to access
private window fields. Each thread owner retains its worker until the thread
finishes, then releases its references and the Qt object.

Paper format and orientation belong to the host. It resolves them into physical
page dimensions before creating settings editors, previews, and PDF exports.
Template compatibility uses optional physical bounds declared in the pack
manifest. The GUI delegates the decision to the central template model using
these dimensions, without format-name or orientation restrictions in templates.
Rendering uses the same supplied dimensions.

The custom paper format stores width and height directly in millimetres and
ignores the orientation selector. The settings form accepts dimensions from
50 to 2000 mm with two decimal places. Editing these fields does not notify the
album; Apply commits both dimensions and emits one consolidated change.
`AlbumStructureSettings.effective_page_format()` resolves named and custom
formats for previews, template editors, and PDF export. Custom dimensions are
project-persisted; older projects retain the standard format behavior.

`PageTemplateSettingsWidget` provides the shared settings layout: scrollable
controls beside a top-aligned preview title and page. Its preview factory keeps
the physical aspect ratio within screen bounds. `PageInstanceDialog` sizes to
its contents; templates supply their controls and rendering without rebuilding
the preview column.

Format and orientation changes refresh compatible choices as one settings
transaction. Loading settings emits no change; a user action emits one change
after all dependent selections have been restored or replaced.

Selected special pages remain in the project when their template is incompatible
with the current page dimensions. Their rows display a warning and disable the
settings button. AlbumBuilder filters them from the effective plan before
pagination, so previews and PDF exports omit them without losing saved order,
instance IDs, or options. Returning to compatible dimensions restores them
automatically. Preview prewarming uses the effective plan as well.

The asynchronous preview cache includes physical page dimensions and derives
its canonical raster aspect ratio from them. The scatter backend excludes title
styling from its background signature: changing the title only repaints the
lightweight overlay, while changing the seed or page geometry requests a new
background.

`tests/test_main_window_components.py` checks component connections, a real scan
of a temporary folder, metadata editing and restoration, selection after sorting,
and background task execution.
