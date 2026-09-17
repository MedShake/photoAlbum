from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from photoalbum import __version__
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import (
    GeocodingError,
    NominatimGeocoder,
    create_nominatim_location_resolver,
)
from photoalbum.scanner import (
    LibraryScanner,
    PhotoProcessor,
    ProcessingEvent,
)

from photoalbum.app import ProjectService
from photoalbum.album import (
    AlbumBuilder,
    PrintConstraints,
    page_format_from_id,
)
from photoalbum.export import (
    PdfExportService,
    PdfMetadata,
)
from photoalbum.i18n import Translator
from photoalbum.template_engine import (
    create_template_registry,
    register_discovered_template_extensions,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-album-cli",
        description="Manage Photo Album project data without modifying source images."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan and analyze a photo directory.",
    )

    scan_parser.add_argument(
        "source",
        type=Path,
        help="Directory containing source photos.",
    )

    scan_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    scan_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subdirectories recursively.",
    )

    scan_parser.add_argument(
        "--language",
        default="fr",
        help="Preferred language for geocoding results.",
    )

    scan_parser.add_argument(
        "--geocode",
        action="store_true",
        help="Enable reverse geocoding.",
    )

    scan_parser.add_argument(
        "--user-agent",
        help="User-Agent used for the geocoding service.",
    )

    scan_parser.add_argument(
        "--nominatim-endpoint",
        default=NominatimGeocoder.DEFAULT_ENDPOINT,
        help="Nominatim reverse-geocoding endpoint.",
    )

    set_date_parser = subparsers.add_parser(
        "set-date",
        help="Set a manual capture date for a project photo.",
    )

    set_date_parser.add_argument(
        "photo",
        type=Path,
        help="Path to the photo.",
    )

    set_date_parser.add_argument(
        "datetime",
        help=(
            "Capture date and time, for example "
            "'2025-07-14 18:30:00'."
        ),
    )

    set_date_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    set_location_parser = subparsers.add_parser(
        "set-location",
        help="Set the editorial location used in the preview and PDF.",
    )

    set_location_parser.add_argument(
        "photo",
        type=Path,
        help="Path to the photo.",
    )

    set_location_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    set_location_parser.add_argument(
        "--text",
        help="Editorial location text; an empty string hides the location.",
    )

    set_location_parser.add_argument(
        "--place",
        help="Manual place name.",
    )

    set_location_parser.add_argument(
        "--city",
        help="Manual city name.",
    )

    set_location_parser.add_argument(
        "--address",
        help="Manual address.",
    )

    refresh_location_parser = subparsers.add_parser(
        "refresh-location",
        help="Force reverse geocoding for a project photo.",
    )

    refresh_location_parser.add_argument(
        "photo",
        type=Path,
        help="Path to the photo.",
    )

    refresh_location_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    refresh_location_parser.add_argument(
        "--language",
        default="fr",
        help="Preferred language for geocoding results.",
    )

    refresh_location_parser.add_argument(
        "--user-agent",
        default=f"PhotoAlbum/{__version__}",
        help="User-Agent used for the geocoding service (default: application ID).",
    )

    refresh_location_parser.add_argument(
        "--nominatim-endpoint",
        default=NominatimGeocoder.DEFAULT_ENDPOINT,
        help="Nominatim reverse-geocoding endpoint.",
    )

    gps_parser = subparsers.add_parser(
        "set-gps", help="Update project GPS coordinates and resolve their location.",
    )
    gps_parser.add_argument("photo", type=Path)
    gps_parser.add_argument("latitude", type=float)
    gps_parser.add_argument("longitude", type=float)
    gps_parser.add_argument("--project", type=Path, required=True)
    gps_parser.add_argument("--language", choices=("fr", "en"), default="fr")
    gps_parser.add_argument("--user-agent", default=f"PhotoAlbum/{__version__}")
    gps_parser.add_argument("--nominatim-endpoint", default=NominatimGeocoder.DEFAULT_ENDPOINT)

    pdf_parser = subparsers.add_parser(
        "pdf",
        help="Generate a PDF from an existing Photo Album project.",
    )

    pdf_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    pdf_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output PDF file.",
    )

    pdf_parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        choices=(150, 300, 600),
        help="PDF rendering resolution (default: 300).",
    )

    pdf_parser.add_argument(
        "--language",
        default="fr",
        choices=("fr", "en"),
        help="Document language (default: fr).",
    )

    pdf_parser.add_argument(
        "--title",
        default="",
        help="PDF title metadata.",
    )

    pdf_parser.add_argument(
        "--author",
        default="",
        help="PDF author metadata.",
    )

    pdf_parser.add_argument(
        "--subject",
        default="",
        help="PDF subject metadata.",
    )

    pdf_parser.add_argument(
        "--keywords",
        default="",
        help="PDF keywords metadata.",
    )

    return parser


def print_event(event: ProcessingEvent) -> None:
    print(
        f"[{event.type.value}] "
        f"{event.path.name}: "
        f"{event.message}"
    )


def create_photo_processor(
    args: argparse.Namespace,
    database: ProjectDatabase,
) -> PhotoProcessor:
    if not args.geocode:
        return PhotoProcessor()

    if not args.user_agent:
        raise ValueError(
            "--user-agent is required when --geocode is enabled."
        )

    resolver = create_nominatim_location_resolver(
        database,
        user_agent=args.user_agent,
        endpoint=args.nominatim_endpoint,
    )

    return PhotoProcessor(
        location_resolver=resolver,
    )


def print_summary(result) -> None:
    statistics = result.statistics

    print()
    print("Scan summary")
    print("------------")
    print(f"Discovered:       {statistics.discovered}")
    print(f"Analyzed:         {statistics.analyzed}")
    print(f"Reused:           {statistics.reused}")
    print(f"Geocoded:         {statistics.geocoded}")
    print(f"Date anomalies:   {statistics.date_anomalies}")
    print(f"Errors:           {statistics.errors}")

    if result.date_anomalies:
        print()
        print("Photos requiring a capture date")
        print("--------------------------------")

        for photo in result.date_anomalies:
            print(photo.path)

    if result.errors:
        print()
        print("Processing errors")
        print("-----------------")

        for error in result.errors:
            print(f"{error.path}: {error.message}")


def parse_manual_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError("Use a local date/time without a timezone, as in the GUI.")
        return parsed
    except ValueError as exc:
        raise ValueError(
            "Invalid date/time. Expected a value such as "
            "'2025-07-14 18:30:00'."
        ) from exc


def normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def open_project(
    project_path: Path,
) -> ProjectDatabase:
    database = ProjectDatabase(project_path)
    database.initialize()

    return database


def run_scan(args: argparse.Namespace) -> int:
    if args.geocode and not args.user_agent:
        print(
            "Error: --user-agent is required when "
            "--geocode is enabled.",
            file=sys.stderr,
        )
        return 2

    source_path = args.source.expanduser().resolve()
    project_path = args.project.expanduser().resolve()

    project_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database = open_project(project_path)

    try:
        repository = PhotoRepository(database)

        processor = create_photo_processor(
            args,
            database,
        )

        scanner = LibraryScanner(
            photo_repository=repository,
            photo_processor=processor,
        )

        try:
            result = scanner.scan(
                source_path,
                recursive=args.recursive,
                language=args.language,
                on_event=print_event,
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(
                f"Error: {exc}",
                file=sys.stderr,
            )
            return 2

        print_summary(result)

        return 0 if not result.errors else 1

    finally:
        database.close()


def run_set_date(args: argparse.Namespace) -> int:
    project_path = args.project.expanduser().resolve()
    photo_path = args.photo.expanduser().resolve()

    if not project_path.exists():
        print(
            f"Error: project does not exist: {project_path}",
            file=sys.stderr,
        )
        return 2

    try:
        capture_datetime = parse_manual_datetime(
            args.datetime
        )
    except ValueError as exc:
        print(
            f"Error: {exc}",
            file=sys.stderr,
        )
        return 2

    database = open_project(project_path)

    try:
        repository = PhotoRepository(database)

        try:
            repository.set_manual_capture_datetime(
                photo_path,
                capture_datetime,
            )
        except KeyError:
            print(
                "Error: photo is not registered in the project: "
                f"{photo_path}",
                file=sys.stderr,
            )
            return 2

        print("Manual capture date updated:")
        print(f"Photo: {photo_path}")
        print(
            "Date:  "
            f"{capture_datetime.isoformat(sep=' ')}"
        )

        return 0

    finally:
        database.close()


def run_set_location(
    args: argparse.Namespace,
) -> int:
    project_path = args.project.expanduser().resolve()
    photo_path = args.photo.expanduser().resolve()

    if not project_path.exists():
        print(
            f"Error: project does not exist: {project_path}",
            file=sys.stderr,
        )
        return 2

    place_name = normalize_optional_text(args.place)
    city = normalize_optional_text(args.city)
    address = normalize_optional_text(args.address)

    if (
        args.text is None
        and place_name is None
        and city is None
        and address is None
    ):
        print(
            "Error: provide --text or at least one of --place, --city or "
            "--address must be provided.",
            file=sys.stderr,
        )
        return 2

    if args.text is not None and any((place_name, city, address)):
        print("Error: --text cannot be combined with --place, --city or --address.", file=sys.stderr)
        return 2
    location_text = (
        normalize_optional_text(args.text) if args.text is not None
        else ", ".join(dict.fromkeys(v for v in (place_name, city, address) if v))
    )

    database = open_project(project_path)

    try:
        repository = PhotoRepository(database)

        try:
            repository.set_editorial_location(
                photo_path, components=(), location_text=location_text,
            )
        except KeyError:
            print(
                "Error: photo is not registered in the project: "
                f"{photo_path}",
                file=sys.stderr,
            )
            return 2

        print("Manual location updated:")
        print(f"Photo:   {photo_path}")
        print(f"Editorial location: {location_text or '-'}")

        return 0

    finally:
        database.close()


def run_set_gps(args: argparse.Namespace) -> int:
    return _run_geocoding(args, update_gps=True)


def run_refresh_location(args: argparse.Namespace) -> int:
    return _run_geocoding(args, update_gps=False)


def _run_geocoding(args: argparse.Namespace, *, update_gps: bool) -> int:
    service = ProjectService()
    photo_path = args.photo.expanduser().resolve()
    try:
        if not args.user_agent.strip():
            raise ValueError("User-Agent must not be empty.")
        service.open(args.project)
        photo = service.find_photo(photo_path)
        if photo is None:
            raise ValueError(f"Photo is not registered in the project: {photo_path}")
        if update_gps:
            service.set_manual_gps(photo_path, args.latitude, args.longitude)
            photo = service.find_photo(photo_path)
            print("GPS coordinates saved in the project; previous geocoding data cleared.")
        if not photo.has_gps:
            raise ValueError("Photo has no GPS coordinates.")
        try:
            # Match the GUI for GPS edits; explicit refresh bypasses the cache.
            location = service.resolve_location(
                photo.latitude, photo.longitude, language=args.language,
                user_agent=args.user_agent, endpoint=args.nominatim_endpoint,
                force_refresh=not update_gps,
            )
        except GeocodingError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            location = None
        if location is None:
            message = "Geographic information could not be resolved."
            if update_gps:
                message += " New GPS coordinates remain saved; previous geocoding data is cleared."
            print(f"Error: {message}", file=sys.stderr)
            return 1
        service.set_geocoded_location(
            photo_path, place_name=location.place_name, city=location.city,
            address=location.address, raw_location_data=location.raw_data,
        )
        print(f"Geographic information updated: {photo_path}")
        print(f"Address: {location.address or '-'}")
        return 0
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        service.close()


def run_pdf(
    args: argparse.Namespace,
) -> int:
    project_path = (
        args.project.expanduser().resolve()
    )

    output_path = (
        args.output.expanduser().resolve()
    )

    if not project_path.exists():
        print(
            f"Error: project does not exist: {project_path}",
            file=sys.stderr,
        )
        return 2

    if args.dpi <= 0:
        print(
            "Error: DPI must be greater than zero.",
            file=sys.stderr,
        )
        return 2

    # PDF rendering uses QPixmap internally. Even though this
    # command has no GUI, Qt requires a QGuiApplication before
    # any QPixmap can be created.
    qt_app = QGuiApplication.instance()

    if qt_app is None:
        qt_app = QGuiApplication(
            ["photo-album-cli", "pdf"]
        )

    service = ProjectService()

    try:
        service.open(project_path)

        settings = (
            service.get_album_structure_settings()
        )

        if settings is None:
            print(
                "Error: the project has no saved album settings.",
                file=sys.stderr,
            )
            return 2

        photos = service.list_photos()

        if not photos:
            print(
                "Error: the project contains no photos.",
                file=sys.stderr,
            )
            return 2

        register_discovered_template_extensions()

        registry = (
            create_template_registry()
        )

        builder = AlbumBuilder(
            registry
        )

        result = builder.build(
            photos,
            settings,
            print_constraints=PrintConstraints(),
        )

        try:
            page_format = page_format_from_id(
                settings.page_format
            )
        except ValueError as exc:
            print(
                f"Error: {exc}",
                file=sys.stderr,
            )
            return 2

        width_mm = page_format.width_mm
        height_mm = page_format.height_mm

        orientation = getattr(
            settings.orientation,
            "value",
            settings.orientation,
        )

        if orientation == "landscape":
            width_mm, height_mm = (
                height_mm,
                width_mm,
            )

        metadata = PdfMetadata(
            title=args.title,
            author=args.author,
            subject=args.subject,
            keywords=args.keywords,
        )

        exporter = PdfExportService(
            Translator(args.language)
        )

        print(f"Project: {project_path}")
        print(f"Output:  {output_path}")
        print(
            f"Format:  {settings.page_format} "
            f"({width_mm:g} x {height_mm:g} mm)"
        )
        print(f"DPI:     {args.dpi}")
        print(f"Photos:  {len(photos)}")
        print(
            "Pages:   "
            f"{result.total_page_count} "
            "(including covers)"
        )
        print()
        print("Generating PDF...")

        exporter.export(
            output_path=output_path,
            result=result,
            settings=settings,
            photos=photos,
            page_width_mm=width_mm,
            page_height_mm=height_mm,
            dpi=args.dpi,
            metadata=metadata,
        )

        print()
        print("PDF generated successfully:")
        print(output_path)

        return 0

    except Exception as exc:
        print(
            f"Error generating PDF: {exc}",
            file=sys.stderr,
        )
        return 1

    finally:
        service.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "pdf":
        return run_pdf(args)

    if args.command == "scan":
        return run_scan(args)

    if args.command == "set-date":
        return run_set_date(args)

    if args.command == "set-gps":
        return run_set_gps(args)

    if args.command == "set-location":
        return run_set_location(args)

    if args.command == "refresh-location":
        return run_refresh_location(args)

    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
