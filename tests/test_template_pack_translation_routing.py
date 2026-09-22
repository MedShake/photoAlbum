from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from photoalbum.album import PageInstance, TemplateDefinition, TemplateKind
from photoalbum.gui.preview_render_service import PreviewRenderService
from photoalbum.gui.template_labels import template_display_name
from photoalbum.gui.template_settings import create_template_settings_editor
from photoalbum.i18n import Translator
from photoalbum.rendering import PageRenderer
from photoalbum.template_engine import (
    discover_template_packs,
    PageTemplateExtension,
    TemplatePack,
    replace_active_template_packs,
    template_extension_registry,
)
from photoalbum.template_engine.discovery import pack_settings_editor


TEMPLATE_ID = "translation-routing-page"
PACK_ID = "translation_routing"
TRANSLATION_KEY = "template.translation-routing-page"


@pytest.fixture
def routed_pack(monkeypatch):
    definition = TemplateDefinition(
        template_id=TEMPLATE_ID,
        name="Fallback name",
        allowed_kinds=frozenset({TemplateKind.SPECIAL_PAGE}),
        pack_id=PACK_ID,
        pack_name="Routing pack",
    )
    pack = TemplatePack(
        pack_id=PACK_ID,
        name="Routing pack",
        version="1",
        path=Path("."),
        description=None,
        authors=(),
        templates=(definition,),
        modules=(),
        translation_catalogs={"fr": {
            TRANSLATION_KEY: "Nom traduit",
            "routing.probe": "Traduction reçue",
        }},
    )
    monkeypatch.setattr(
        template_extension_registry,
        "_extensions",
        dict(template_extension_registry._extensions),
    )
    replace_active_template_packs((pack,))
    yield definition
    replace_active_template_packs(discover_template_packs())


def assert_pack_translator(translator):
    assert translator.tr("routing.probe") == "Traduction reçue"


def test_settings_editor_receives_its_pack_translator(routed_pack):
    received = []

    class Editor:
        def __init__(self, instance, photos, *, translator, **kwargs):
            received.append(translator)

    template_extension_registry.register(PageTemplateExtension(
        template_id=TEMPLATE_ID,
        settings_editor_type=Editor,
    ))

    create_template_settings_editor(
        TEMPLATE_ID,
        PageInstance(template_id=TEMPLATE_ID),
        (),
        translator=Translator("fr"),
    )

    assert_pack_translator(received[0])


def test_page_renderer_receives_its_pack_translator(routed_pack):
    received = []

    class Renderer:
        def paint(self, **kwargs):
            received.append(kwargs["translator"])

    template_extension_registry.register(PageTemplateExtension(
        template_id=TEMPLATE_ID,
        widget_renderer=Renderer(),
    ))
    composition = SimpleNamespace(
        page=SimpleNamespace(
            template_id=TEMPLATE_ID,
            page_instance=PageInstance(template_id=TEMPLATE_ID),
            photos=(),
        ),
        photo_slots=(),
    )

    rendered = PageRenderer(translator=Translator("fr"))._paint_template_page(
        painter=None,
        composition=composition,
        target_rect=None,
        width=100,
        height=100,
        page_width_mm=100,
        page_height_mm=100,
        font_pixel_size=None,
        pixel_rect=None,
        thumbnail_cache=None,
        album_pages=(),
        template_pack_settings=None,
        render_service=None,
        set_waiting_key=None,
        show_empty_slots=False,
    )

    assert rendered is True
    assert_pack_translator(received[0])


def test_async_preview_backend_receives_its_pack_translator(routed_pack):
    class ExpectedCall(Exception):
        pass

    class Backend:
        def effective_photos(self, instance, photos):
            return tuple(photos)

        def render_settings_signature(self, instance):
            return instance.settings

        def create_job(self, **kwargs):
            assert_pack_translator(kwargs["translator"])
            raise ExpectedCall

    template_extension_registry.register(PageTemplateExtension(
        template_id=TEMPLATE_ID,
        preview_backend=Backend(),
    ))
    service = PreviewRenderService(Translator("fr"))

    with pytest.raises(ExpectedCall):
        service.request(
            PageInstance(template_id=TEMPLATE_ID),
            (),
            width=100,
            height=100,
            page_width_mm=210,
            page_height_mm=297,
        )


def test_template_label_comes_from_its_pack_catalog(routed_pack):
    assert template_display_name(
        routed_pack, Translator("fr")
    ) == "Routing pack — Nom traduit"


def test_pack_settings_editor_receives_its_pack_translator(
    routed_pack, monkeypatch
):
    module_name = f"photoalbum.templates.{PACK_ID}"
    module = ModuleType(module_name)

    def edit_settings(settings, *, translator, parent=None):
        assert_pack_translator(translator)
        return settings

    module.edit_settings = edit_settings
    monkeypatch.setitem(sys.modules, module_name, module)

    editor = pack_settings_editor(PACK_ID)

    assert editor is not None
    assert editor({}, translator=Translator("fr")) == {}
