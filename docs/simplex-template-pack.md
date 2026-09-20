# Simplex template pack

The **Simplex** template pack contains deliberately minimal page
templates.

Its first template is `simplex-full-photo-cover`, a full-page
photographic front cover.

## Full-page photo cover

The template is available for the **front cover** only.

The template declares no geometric bounds. The host supplies physical page
width and height; named formats and orientations do not restrict compatibility.

The image fills the complete page without margins. Its aspect ratio
is preserved. When the image and page ratios differ, the image is
scaled to cover the page and the excess is cropped symmetrically.

## Image sources

The cover supports two image-source modes.

### Project photo

A photo already present in the project can be selected.

Using a project photo for the cover does not remove it from the album
or reserve it exclusively for the cover. It remains available to the
normal album composition.

### External file

An image can instead be selected directly from the filesystem.

The external image is used by the cover without being added to the
project's photo collection.

As with the application's existing source-photo model, the project
keeps a reference to the source path. Moving or deleting the referenced
file can therefore make the image unavailable.

## Settings UI

Template settings follow the common two-column convention:

- settings and image-source selection on the left;
- live template preview on the right.

Changing the project photo, switching source mode, or selecting an
external image updates the preview immediately.

## Template-pack integration

Simplex is discovered through the standard template-pack mechanism.
Its executable behaviour is registered as a template extension rather
than being implemented as a Simplex-specific branch in the main GUI.

Cover choices are filtered by both:

- physical cover position;
- current page format and orientation.

See `docs/template-packs.md` for the general pack architecture and
`docs/gui-architecture.md` for GUI responsibilities.
