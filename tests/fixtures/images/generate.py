"""Reproduce our synthetic fixtures: .venv/bin/python tests/fixtures/images/generate.py.

No camera photos or third-party images. Keep these real HEVC files checked in;
tests and release checks must exercise decoding without needing an encoder.
"""
from pathlib import Path
from struct import pack

from PIL import Image, ImageCms, ImageDraw
from PIL.TiffImagePlugin import IFDRational
from pillow_heif import from_bytes, register_heif_opener


def pattern():
    image = Image.new("RGB", (96, 64))
    draw = ImageDraw.Draw(image)
    for box, color in (
        ((0, 0, 47, 31), (220, 30, 40)),
        ((48, 0, 95, 31), (30, 180, 60)),
        ((0, 32, 47, 63), (40, 60, 210)),
        ((48, 32, 95, 63), (230, 200, 40)),
    ):
        draw.rectangle(box, fill=color)
    return image


def generate():
    register_heif_opener()
    root = Path(__file__).parent
    for orientation in range(1, 9):
        exif = Image.Exif()
        exif[274] = orientation
        exif[306] = "2025:02:01 00:00:00"
        exif[34665] = {36867: "2024:06:15 12:34:56"}
        exif[34853] = {
            1: "N", 2: (IFDRational(48), IFDRational(30), IFDRational(0)),
            3: "W", 4: (IFDRational(2), IFDRational(15), IFDRational(0)),
        }
        pattern().save(root / f"orientation-{orientation}.heic", exif=exif.tobytes(),
                       quality=-1, chroma=444,
                       icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    pattern().save(root / "no-exif.heif", quality=-1, chroma=444)
    alpha = pattern().convert("RGBA")
    alpha.putalpha(128)
    alpha.save(root / "alpha.heic", quality=-1, chroma=444)
    # A genuine 10-bit HEVC stream; the rendering contract is RGB8 SDR.
    image = pattern()
    high_bit = from_bytes("RGB;16", image.size,
                         b"".join(pack("<H", value * 257) for value in image.tobytes()))
    high_bit.save(root / "ten-bit.heic", quality=-1, chroma=444)
    image.save(root / "display-p3.heic", quality=-1, chroma=444,
               color_primaries=12, transfer_characteristic=13)


if __name__ == "__main__":
    generate()
