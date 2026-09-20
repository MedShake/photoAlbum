# MSB

MSB is the original template pack bundled with Photo Album.

Its `manifest.json` file is the source of truth for the template
catalog.

## Physical page compatibility

Most MSB templates declare no geometric bounds. The classic month divider requires
at least 130 × 145 mm; the calendar index requires at least 110 × 260 mm. The application resolves
paper format and orientation into physical dimensions; templates do not restrict
named formats or orientations. Page kinds and cover positions remain enforced.

An album can freely mix MSB templates with templates from other
installed packs.

## Documentation

The complete documentation for the templates, shared MSB theme,
settings, rendering architecture, and catalog is available in:

    docs/msb-template-pack.md

For the general template-pack API and instructions for creating a new
pack, see:

    docs/template-packs.md

## Screenshots

The `screenshots/` directory is reserved for future screenshots
intended for Photo Album's built-in catalog.
