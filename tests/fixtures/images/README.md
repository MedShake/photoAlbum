These are real HEVC-encoded HEIF containers, generated from a four-color
synthetic pattern owned by this project. They share the project's GPL-3.0-or-later
license and contain no personal photographs or personal metadata.

Regenerate with `python tests/fixtures/images/generate.py` after installing the
project. Generation needs the x265 encoder supplied in the pillow-heif wheel;
running the tests needs only the decoder. Binary files are committed test inputs,
so a broken or missing encoder cannot silently skip HEIC decoding tests.

- `orientation-1.heic` through `orientation-8.heic`: all EXIF orientations,
  matching container rotations/mirrors, sRGB ICC, nested DateTimeOriginal
  2024-06-15 12:34:56 (before root DateTime), GPS 48.5 N / 2.25 W.
- `no-exif.heif`: no EXIF, NCLX sRGB, 96 × 64 pixels.
- `alpha.heic`: RGBA with constant alpha 128.
- `ten-bit.heic`: actual 10-bit HEVC stream decoded into the RGB8 SDR pipeline.
- `display-p3.heic`: NCLX Display P3, sRGB transfer, no ICC profile.

The top-left quadrant before rotation is red, top-right green, bottom-left blue,
bottom-right yellow. Orientation 6 is 64 × 96, with blue at the top-left; this
fixture is also used to verify both compiled executables on Linux and Windows.
