from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import (
    GeocodingCache,
    LocationResolver,
    NominatimGeocoder,
)
from photoalbum.scanner import (
    LibraryScanner,
    PhotoProcessor,
    ProcessingEvent,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Development CLI for Photo Album."
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

    cache = GeocodingCache(database)

    geocoder = NominatimGeocoder(
        user_agent=args.user_agent,
        endpoint=args.nominatim_endpoint,
    )

    resolver = LocationResolver(
        cache,
        geocoder,
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
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "Invalid date/time. Expected a value such as "
            "'2025-07-14 18:30:00'."
        ) from exc


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

    database = ProjectDatabase(project_path)

    try:
        database.initialize()

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

    database = ProjectDatabase(project_path)

    try:
        database.initialize()

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

        print(
            "Manual capture date updated:"
        )
        print(f"Photo: {photo_path}")
        print(
            "Date:  "
            f"{capture_datetime.isoformat(sep=' ')}"
        )

        return 0

    finally:
        database.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        return run_scan(args)

    if args.command == "set-date":
        return run_set_date(args)

    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())