"""Decode originals directly into oriented, color-managed in-memory pixels."""
from io import BytesIO
import logging
from pathlib import Path

from PIL import Image, ImageCms, ImageOps
from pillow_heif import register_heif_opener

from .formats import FORMATS


# Registration happens once under Python's import lock, before worker threads
# start. Never substitute an embedded, potentially lower-quality HEIF thumbnail.
register_heif_opener(thumbnails=False, depth_images=False, aux_images=False)
_PILLOW_FORMATS = tuple(fmt.name for fmt in FORMATS)
_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
_LOGGER = logging.getLogger(__name__)


def open_image(path: str | Path) -> Image.Image:
    """Open by signature, including JPEG provider thumbnails named *.heic.

    Caller owns the Pillow image and must close it. The HEIF plugin opens
    the primary image and libheif applies container rotation/mirroring; its EXIF
    orientation is reset, so exif_transpose must not apply it a second time.
    TIFF is also loaded here: Pillow exposes visual dimensions before loading,
    but only normalizes the EXIF orientation when loading its pixels.
    """
    image = Image.open(path, formats=_PILLOW_FORMATS)
    if image.format in {"HEIF", "TIFF"}:
        # libheif can change size on load (irot/clap). Its pre-load size is
        # insufficient for metadata/layout and for calculating a pixel budget.
        # TIFF must finish its automatic transpose before either consumer reads
        # dimensions + orientation, otherwise axes would be swapped twice.
        try:
            image.load()
        except Exception:
            image.close()
            raise
    return image


def _to_srgb(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A") if image.mode in {"RGBA", "LA", "PA"} else None
    mode = "RGBA" if alpha is not None or "transparency" in image.info else "RGB"
    profile = image.info.get("icc_profile")
    nclx = image.info.get("nclx_profile", {})
    if not profile and nclx:
        primaries = nclx.get("color_primaries")
        transfer = nclx.get("transfer_characteristics")
        if primaries == 12 and transfer == 13:
            profile = (Path(__file__).parent / "profiles" / "DisplayP3-v4.icc").read_bytes()
        elif (primaries, transfer) not in {(1, 13), (2, 2)}:
            _LOGGER.warning("Unsupported NCLX primaries/transfer %s/%s; using sRGB SDR fallback",
                            primaries, transfer)
    if profile:
        try:
            # LittleCMS accepts RGB, CMYK and grayscale profiles. Palette and
            # alpha images need an RGB base; preserve alpha without transforming it.
            base = image if image.mode in {"RGB", "CMYK", "L", "LAB"} else image.convert("RGB")
            result = ImageCms.profileToProfile(
                base, ImageCms.ImageCmsProfile(BytesIO(profile)), _SRGB, outputMode="RGB",
            )
            if alpha is not None:
                result.putalpha(alpha)
            elif mode == "RGBA":
                result.putalpha(image.convert("RGBA").getchannel("A"))
            return result
        except (ImageCms.PyCMSError, OSError, ValueError, TypeError):
            _LOGGER.warning("Invalid/unsupported ICC profile; treating pixels as sRGB")
    # Untagged images use sRGB, matching the application's existing RGB output.
    return image.convert(mode)


def decode_image(
    path: str | Path,
    target_size: tuple[int, int] | None = None,
    *,
    fit: str = "contain",
) -> Image.Image:
    """Return detached RGB(A) sRGB pixels; never write or re-encode an original.

    target_size is a pixel budget. 'cover' keeps enough pixels to fill a crop;
    neither mode upsamples. JPEG draft decoding reduces memory before loading.
    Without a budget, all original pixels are decoded. Rendering is currently
    8-bit SDR, including the HEIF plugin's 10/12-bit to 8-bit decoding.
    """
    if fit not in {"contain", "cover"}:
        raise ValueError(f"Unsupported image fit: {fit}")
    if target_size is not None and min(target_size) <= 0:
        raise ValueError("Image target dimensions must be positive")
    with open_image(path) as source:
        orientation = source.getexif().get(274)
        size = source.size[::-1] if orientation in (5, 6, 7, 8) else source.size
        budget = None
        if target_size is not None:
            ratios = (target_size[0] / size[0], target_size[1] / size[1])
            scale = min(1.0, max(ratios) if fit == "cover" else min(ratios))
            budget = (max(1, round(size[0] * scale)), max(1, round(size[1] * scale)))
            raw_budget = budget[::-1] if orientation in (5, 6, 7, 8) else budget
            source.draft(None, raw_budget)
        ImageOps.exif_transpose(source, in_place=True)
        if budget is not None:
            source.thumbnail(budget, Image.Resampling.LANCZOS)
        result = _to_srgb(source)
        # No stale source profile or orientation survives a normalized decode.
        result.info.pop("exif", None)
        result.info.pop("nclx_profile", None)
        result.info.pop("original_orientation", None)
        result.info["icc_profile"] = _SRGB.tobytes()
        return result
