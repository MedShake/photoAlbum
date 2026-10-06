# MSB

[Français](README.fr.md) | **English**

MSB is the default template pack bundled with Photo Album.

Its `manifest.json` file is the source of truth for the template
catalog.

## Physical page compatibility

Most MSB templates declare no geometric bounds. The classic month divider requires
at least 130 × 145 mm; the calendar index requires at least 180 × 180 mm. The application resolves
paper format and orientation into physical dimensions; templates do not restrict
named formats or orientations. Page kinds and cover positions remain enforced.

An album can freely mix MSB templates with templates from other
installed packs.

## Documentation

The complete documentation for the templates, shared MSB theme,
settings, rendering architecture, and catalog is available in:

    docs/developer.md
    docs/developer.fr.md

For shared contracts and pack authoring, see [the wiki](https://github.com/MedShake/photoAlbum/wiki/Template-packs).
