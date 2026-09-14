from __future__ import annotations

import argparse
import sys
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

    parser.add_argument(
        "source",
        type=Path,
        help="Directory containing source photos.",
    )

    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to the .photoalbum project file.",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subdirectories recursively.",
    )

    parser.add_argument(
        "--language",
        default="fr",
        help="Preferred language for geocoding results.",
    )

    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Enable reverse geocoding.",
    )

    parser.add_argument(
        "--user-agent",
        help="User-Agent used for the geocoding service.",
    )

    parser.add_argument(
        "--nominatim-endpoint",
        default=NominatimGeocoder.DEFAULT_ENDPOINT,
        help="Nominatim reverse-geocoding endpoint.",
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.geocode and not args.user_agent:
        parser.error(
            "--user-agent is required when --geocode is enabled."
        )

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


if __name__ == "__main__":
    raise SystemExit(main())

