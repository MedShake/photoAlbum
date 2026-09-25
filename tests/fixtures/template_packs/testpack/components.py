"""Everything specific to this pack lives in this directory."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QSpinBox, QVBoxLayout, QLabel

from photoalbum.template_engine.api import (
    NormalizedRect, PageComposition, PhotoSlotComposition, PageTemplateSettingsWidget,
    PageTemplateExtension, register_template_extension, TemplatePreviewBackend, PreviewJob,
)

render_calls = []
preview_calls = []
layout_calls = []


def defaults():
    return {"banana_density": 17, "caption_style": "foo", "nested": {"values": [1, 2]}}


def validate(settings):
    if not isinstance(settings.get("banana_density"), int) or settings["banana_density"] < 0:
        raise ValueError("Invalid banana density")


def color(settings):
    palette = json.loads((Path(__file__).parent / "assets/palette.json").read_text())
    return QColor(palette["dense" if settings["banana_density"] >= 20 else "sparse"])


class Editor(PageTemplateSettingsWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._translator.tr("banana.settings")))
        self.density = QSpinBox()
        self.density.setValue(self._instance.settings["banana_density"])
        self.density.valueChanged.connect(self.changed)
        layout.addWidget(self.density)

    def changed(self, value):
        self._instance = self._instance.with_settings({**self._instance.settings, "banana_density": value})
        self.instance_changed.emit()


class Renderer:
    def paint(self, *, painter, instance, target_rect, translator, template_pack_settings, **kwargs):
        assert kwargs['composition'].photo_slots[0].image_rect.x == instance.settings['banana_density'] / 100
        render_calls.append((dict(instance.settings), translator.tr("banana.label"), template_pack_settings))
        painter.fillRect(target_rect, color(instance.settings))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(target_rect, Qt.AlignmentFlag.AlignCenter, translator.tr("banana.label"))


class Layout:
    def compose(self, page, instance, page_numbers, **kwargs):
        layout_calls.append(dict(instance.settings))
        margin = instance.settings["banana_density"] / 100
        return PageComposition(page=page, photo_slots=(PhotoSlotComposition(
            image_rect=NormalizedRect(margin, margin, 1 - 2 * margin, 1 - 2 * margin),
            caption_rect=None, caption={"style": instance.settings["caption_style"]},
        ),))


class Signals(QObject):
    finished = Signal(str, bytes)
    failed = Signal(str, str)


class Worker(QRunnable):
    def __init__(self, request_id, settings):
        super().__init__()
        self.signals = Signals()
        self.request_id = request_id
        self.settings = settings

    def run(self):
        self.signals.finished.emit(self.request_id, json.dumps(self.settings).encode())


class Preview(TemplatePreviewBackend):
    template_id = "testpack-page"

    def create_job(self, *, request_id, instance, translator, **kwargs):
        preview_calls.append((dict(instance.settings), translator.tr("banana.label")))

        def finalize(data):
            settings = json.loads(data)
            pixmap = QPixmap(20, 20)
            pixmap.fill(color(settings))
            return pixmap

        return PreviewJob(worker=Worker(request_id, dict(instance.settings)), finalize=finalize)


def edit_pack(settings, *, translator, parent=None):
    return {**settings, "testpack": {"label": translator.tr("banana.label")}}


def register():
    register_template_extension(PageTemplateExtension(
        template_id="testpack-page", widget_renderer=Renderer(), settings_editor_type=Editor,
        preview_backend=Preview(), settings_defaults=defaults, validate_settings=validate,
    ))


def register_layouts(registry):
    registry.register("testpack-page", Layout())
