from __future__ import annotations


class BlankWidgetRenderer:
    """Renderer for an intentionally blank page."""

    def paint(
        self,
        *,
        painter,
        instance,
        photos,
        target_rect,
        width,
        height,
        translator,
        render_service=None,
        set_waiting_key=None,
        font_pixel_size=None,
        page_width_mm=None,
        page_height_mm=None,
        album_pages=(),
        thumbnail_cache=None,
        pixel_rect=None,
        composition=None,
        template_pack_settings=None,
        **kwargs,
    ) -> None:
        # Intentionally paint nothing.
        #
        # The page background is supplied by the common rendering
        # pipeline. A blank template must therefore remain blank in
        # previews as well as in exported PDFs.
        return None
