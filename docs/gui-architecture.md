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

`tests/test_main_window_components.py` checks component connections, a real scan
of a temporary folder, metadata editing and restoration, selection after sorting,
and background task execution.
