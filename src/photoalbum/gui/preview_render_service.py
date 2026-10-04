from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QPixmap

from photoalbum.album import PageInstance
from photoalbum.template_engine import (
    template_extension_registry,
    translator_for_template,
)
from photoalbum.template_engine.preview_backend import (
    PreviewJob,
)
from photoalbum.i18n import Translator


# Canonical portrait raster size for expensive preview rendering.
#
# The long edge is fixed; the aspect ratio follows physical page dimensions.
# Consumers can reuse a background regardless of their display size.
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
    page_width_mm: float
    page_height_mm: float


class PreviewRenderService(QObject):
    """
    Shared asynchronous preview cache.

    Important:
    Worker request_id remains a plain str because the preview
    protocol uses Qt signals with a string identifier.

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
            QRunnable,
        ] = {}

        self._request_keys: dict[
            str,
            PreviewRenderKey,
        ] = {}

        self._request_jobs: dict[
            str,
            PreviewJob,
        ] = {}

        self._thread_pool = (
            QThreadPool.globalInstance()
        )

    @staticmethod
    def _settings_signature(
        instance: PageInstance,
        *,
        template_pack_settings=None,
    ) -> str:
        extension = (
            template_extension_registry.get(
                instance.template_id
            )
        )

        backend = (
            extension.preview_backend
            if extension is not None
            else None
        )

        if backend is None:
            value = instance.settings
        else:
            try:
                value = backend.render_settings_signature(
                    instance,
                    template_pack_settings=template_pack_settings,
                )
            except TypeError as exc:
                if (
                    "unexpected keyword argument"
                    not in str(exc)
                    or "template_pack_settings"
                    not in str(exc)
                ):
                    raise

                # Compatibility with preview backends implementing
                # the original API.
                value = backend.render_settings_signature(
                    instance
                )

        # repr is sufficient here because this is an in-memory
        # cache key, not a persistent serialization format.
        return sha256(
            repr(value).encode(
                "utf-8"
            )
        ).hexdigest()

    def effective_photos(
        self,
        instance: PageInstance,
        photos,
    ) -> tuple:
        extension = (
            template_extension_registry.get(
                instance.template_id
            )
        )

        if (
            extension is not None
            and extension.preview_backend
            is not None
        ):
            return (
                extension.preview_backend
                .effective_photos(
                    instance,
                    photos,
                )
            )

        # Generic fallback.
        unique = {}

        for photo in photos:
            unique.setdefault(
                photo.identity,
                photo,
            )

        return tuple(
            sorted(
                unique.values(),
                key=lambda photo: photo.identity,
            )
        )


    @staticmethod
    def _photos_signature(
        photos,
        *,
        backend=None,
    ) -> str:
        """
        Stable signature for a set of photos.

        The same photos must produce the same cache key
        independently of repository or album-plan ordering.
        """

        digest = sha256()

        normalized = sorted(
            photos,
            key=lambda photo: photo.identity,
        )

        for photo in normalized:
            digest.update(
                photo.identity.encode(
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

            # Metadata edits can change the expensive raster without
            # changing the source file's modification time.
            if backend is not None:
                photo_state = backend.photo_signature(
                    photo
                )
            else:
                photo_state = (
                    photo.filename,
                    photo.capture_datetime,
                    photo.width,
                    photo.height,
                    photo.orientation,
                )

            digest.update(
                repr(photo_state).encode(
                    "utf-8",
                    errors="replace",
                )
            )
            digest.update(b"\0")

        return digest.hexdigest()


    def supports(
        self,
        template_id: str,
    ) -> bool:
        extension = (
            template_extension_registry.get(
                template_id
            )
        )

        return (
            extension is not None
            and extension.preview_backend
            is not None
        )

    def key_for(
        self,
        instance: PageInstance,
        photos,
        *,
        width: int | None = None,
        height: int | None = None,
        page_width_mm: float,
        page_height_mm: float,
        template_pack_settings=None,
    ) -> PreviewRenderKey:
        photos = self.effective_photos(
            instance,
            photos,
        )

        extension = (
            template_extension_registry.get(
                instance.template_id
            )
        )

        backend = (
            extension.preview_backend
            if extension is not None
            else None
        )

        # Keep one canonical resolution per physical geometry, independent
        # of widget size. A portrait raster stretched onto a landscape page
        # would distort photographs even with correctly composed positions.
        page_width_mm = float(page_width_mm)
        page_height_mm = float(page_height_mm)
        if page_width_mm <= 0 or page_height_mm <= 0:
            raise ValueError("Preview page dimensions must be positive.")
        scale = PREVIEW_RENDER_HEIGHT / max(page_width_mm, page_height_mm)
        return PreviewRenderKey(
            template_id=(
                instance.template_id
            ),
            instance_id=(
                instance.instance_id
            ),
            settings_signature=(
                self._settings_signature(
                    instance,
                    template_pack_settings=template_pack_settings,
                )
            ),
            photos_signature=(
                self._photos_signature(
                    photos,
                    backend=backend,
                )
            ),
            width=max(1, round(page_width_mm * scale)),
            height=max(1, round(page_height_mm * scale)),
            page_width_mm=float(page_width_mm),
            page_height_mm=float(page_height_mm),
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

    def request(
        self,
        instance: PageInstance,
        photos,
        *,
        width: int,
        height: int,
        page_width_mm: float,
        page_height_mm: float,
        template_pack_settings=None,
    ) -> PreviewRenderKey:
        extension = (
            template_extension_registry.get(
                instance.template_id
            )
        )

        backend = (
            extension.preview_backend
            if extension is not None
            else None
        )

        photos = self.effective_photos(
            instance,
            photos,
        )

        key = self.key_for(
            instance,
            photos,
            width=width,
            height=height,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            template_pack_settings=template_pack_settings,
        )

        if key in self._cache:

            return key

        if key in self._pending:

            return key

        # A template without an expensive preview backend simply
        # has nothing to schedule here.
        if backend is None:
            return key

        # Worker-facing identifiers remain plain strings because
        # Qt signals must never carry PreviewRenderKey directly.
        request_id = uuid4().hex

        create_job_kwargs = {
            "request_id": request_id,
            "instance": instance,
            "photos": photos,
            "width": key.width,
            "height": key.height,
            "page_width_mm": key.page_width_mm,
            "page_height_mm": key.page_height_mm,
            "translator": translator_for_template(
                instance.template_id, self._translator
            ),
        }

        from inspect import signature

        create_job_parameters = signature(
            backend.create_job
        ).parameters

        if (
            "template_pack_settings"
            in create_job_parameters
        ):
            job = backend.create_job(
                **create_job_kwargs,
                template_pack_settings=template_pack_settings,
            )
        else:
            # Backwards compatibility with existing expensive
            # preview backends implementing the original interface.
            job = backend.create_job(
                **create_job_kwargs,
            )

        worker = job.worker

        worker.signals.finished.connect(
            self._render_finished
        )

        worker.signals.failed.connect(
            self._render_failed
        )



        self._pending.add(
            key
        )

        self._request_keys[
            request_id
        ] = key

        self._request_jobs[
            request_id
        ] = job

        # Strong reference until QRunnable completion.
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

        job = self._request_jobs.pop(
            request_id,
            None,
        )

        self._workers.pop(
            request_id,
            None,
        )

        if (
            key is None
            or job is None
        ):
            return

        self._pending.discard(
            key
        )

        pixmap = job.finalize(
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

        self._request_jobs.pop(
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

    def clear(
        self,
    ) -> None:
        self._cache.clear()

        # Do not kill running QRunnables. Forgetting their
        # request mapping makes their eventual result harmless.
        self._pending.clear()
        self._request_keys.clear()
        self._request_jobs.clear()
