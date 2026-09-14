from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from PySide6.QtCore import (
    QObject,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QPixmap

from photoalbum.album import PageInstance
from photoalbum.album.cover_scatter import (
    compose_cover_scatter,
    visible_cover_scatter_items,
)
from photoalbum.gui.cover_render_worker import (
    CoverRenderWorker,
)
from photoalbum.i18n import Translator


# Canonical raster size for expensive preview rendering.
#
# Every consumer uses the same size, so a background-prewarmed
# image can be reused by widgets of different display sizes.
PREVIEW_RENDER_WIDTH = 420
PREVIEW_RENDER_HEIGHT = 594


@dataclass(frozen=True)
class PreviewRenderKey:
    template_id: str
    instance_id: str
    settings_signature: str
    photos_signature: str
    width: int
    height: int


class PreviewRenderService(QObject):
    """
    Shared asynchronous preview cache.

    Important:
    CoverRenderWorker request_id remains a plain str because
    its Qt signals are typed for a string identifier.

    PreviewRenderKey never crosses the worker Qt signal.
    """

    preview_ready = Signal(object)
    preview_failed = Signal(object, str)

    def __init__(
        self,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )

        self._translator = translator

        self._cache: dict[
            PreviewRenderKey,
            QPixmap,
        ] = {}

        self._pending: set[
            PreviewRenderKey
        ] = set()

        self._workers: dict[
            str,
            CoverRenderWorker,
        ] = {}

        self._request_keys: dict[
            str,
            PreviewRenderKey,
        ] = {}

        self._thread_pool = (
            QThreadPool.globalInstance()
        )

    @staticmethod
    def _settings_signature(
        instance: PageInstance,
    ) -> str:
        # repr is sufficient here because this is an in-memory
        # cache key, not a persistent serialization format.
        value = repr(
            instance.settings
        )

        return sha256(
            value.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _effective_photos(
        instance: PageInstance,
        photos,
    ) -> tuple:
        """
        Return only the photos that can actually influence
        the rendered template.

        Cache keys must depend on effective template input,
        not on unrelated photos present in the library.
        """

        unique = {}

        for photo in photos:
            key = str(
                photo.path
            )

            unique.setdefault(
                key,
                photo,
            )

        result = list(
            unique.values()
        )

        if (
            instance.template_id
            == "year-photo-scatter"
        ):
            # The scatter represents the dated period of the
            # album. Undated anomalies cannot participate.
            result = [
                photo
                for photo in result
                if photo.capture_datetime
                is not None
            ]

        return tuple(
            sorted(
                result,
                key=lambda photo: str(
                    photo.path
                ),
            )
        )

    @staticmethod
    def _photos_signature(
        photos,
    ) -> str:
        """
        Stable signature for a set of photos.

        The same photos must produce the same cache key
        independently of repository or album-plan ordering.
        """

        digest = sha256()

        normalized = sorted(
            photos,
            key=lambda photo: str(
                photo.path
            ),
        )

        for photo in normalized:
            digest.update(
                str(
                    photo.path
                ).encode(
                    "utf-8",
                    errors="replace",
                )
            )

            digest.update(
                b"\0"
            )

            if (
                photo.modified_time_ns
                is not None
            ):
                digest.update(
                    str(
                        photo.modified_time_ns
                    ).encode(
                        "ascii"
                    )
                )

            digest.update(
                b"\0"
            )

        return digest.hexdigest()


    def key_for(
        self,
        instance: PageInstance,
        photos,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> PreviewRenderKey:
        photos = self._effective_photos(
            instance,
            photos,
        )

        # Expensive previews are always generated at one
        # canonical raster size. Widget display dimensions must
        # never create another cache entry for the same page.
        return PreviewRenderKey(
            template_id=(
                instance.template_id
            ),
            instance_id=(
                instance.instance_id
            ),
            settings_signature=(
                self._settings_signature(
                    instance
                )
            ),
            photos_signature=(
                self._photos_signature(
                    photos
                )
            ),
            width=PREVIEW_RENDER_WIDTH,
            height=PREVIEW_RENDER_HEIGHT,
        )


    def cached(
        self,
        key: PreviewRenderKey,
    ) -> QPixmap | None:
        pixmap = self._cache.get(
            key
        )

        if pixmap is None:
            return None

        return QPixmap(
            pixmap
        )

    def is_pending(
        self,
        key: PreviewRenderKey,
    ) -> bool:
        return key in self._pending

    def request(
        self,
        instance: PageInstance,
        photos,
        *,
        width: int,
        height: int,
    ) -> PreviewRenderKey:
        photos = self._effective_photos(
            instance,
            photos,
        )

        key = self.key_for(
            instance,
            photos,
            width=width,
            height=height,
        )

        if key in self._cache:
            print(
                "[preview-cache] HIT",
                key.template_id,
                key.instance_id,
            )
            return key

        if key in self._pending:
            print(
                "[preview-cache] PENDING",
                key.template_id,
                key.instance_id,
            )
            return key

        if (
            instance.template_id
            != "year-photo-scatter"
        ):
            return key

        scatter = instance.settings.get(
            "scatter",
            {},
        )

        if not isinstance(
            scatter,
            dict,
        ):
            scatter = {}

        seeds = [
            int(value)
            for value in scatter.get(
                "seeds",
                [0],
            )
        ] or [0]

        index = int(
            scatter.get(
                "selected_seed_index",
                0,
            )
        )

        index = min(
            max(
                index,
                0,
            ),
            len(seeds) - 1,
        )

        composition = compose_cover_scatter(
            list(
                photos
            ),
            seed=seeds[index],
            month_name=(
                self._translator.month_name
            ),
        )

        # Worker-facing ID MUST remain a simple string.
        request_id = uuid4().hex

        worker = CoverRenderWorker(
            request_id=request_id,
            width=key.width,
            height=key.height,
            items=visible_cover_scatter_items(
                composition.items
            ),
        )

        worker.signals.finished.connect(
            self._render_finished
        )

        worker.signals.failed.connect(
            self._render_failed
        )

        print(
            "[preview-cache] MISS -> RENDER",
            key.template_id,
            key.instance_id,
            "settings=" + key.settings_signature[:10],
            "photos=" + key.photos_signature[:10],
            f"size={key.width}x{key.height}",
            f"effective_count={len(photos)}",
        )

        self._pending.add(
            key
        )

        self._request_keys[
            request_id
        ] = key

        # Strong reference until completion.
        self._workers[
            request_id
        ] = worker

        self._thread_pool.start(
            worker
        )

        return key

    def _render_finished(
        self,
        request_id: str,
        data: bytes,
    ) -> None:
        key = self._request_keys.pop(
            request_id,
            None,
        )

        self._workers.pop(
            request_id,
            None,
        )

        if key is None:
            return

        self._pending.discard(
            key
        )

        pixmap = QPixmap()

        pixmap.loadFromData(
            data
        )

        if pixmap.isNull():
            self.preview_failed.emit(
                key,
                "Invalid preview image",
            )
            return

        self._cache[
            key
        ] = pixmap

        self.preview_ready.emit(
            key
        )

    def _render_failed(
        self,
        request_id: str,
        message: str,
    ) -> None:
        key = self._request_keys.pop(
            request_id,
            None,
        )

        self._workers.pop(
            request_id,
            None,
        )

        if key is None:
            return

        self._pending.discard(
            key
        )

        self.preview_failed.emit(
            key,
            message,
        )

    def invalidate_instance(
        self,
        instance_id: str,
    ) -> None:
        for key in list(
            self._cache
        ):
            if (
                key.instance_id
                == instance_id
            ):
                del self._cache[
                    key
                ]

    def clear(
        self,
    ) -> None:
        self._cache.clear()

        # Do not kill running QRunnables. Forgetting their
        # request mapping makes their eventual result harmless.
        self._pending.clear()
        self._request_keys.clear()
