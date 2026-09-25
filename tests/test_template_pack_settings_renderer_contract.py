"""All rendering paths pass the same opaque context without signature guessing."""
from types import SimpleNamespace

import pytest

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.rendering import PageRenderer
from photoalbum.template_engine import PageTemplateExtension, template_extension_registry


@pytest.mark.parametrize('scope', ['page', 'album'])
@pytest.mark.parametrize('kind', ['photo_group', 'special_page', 'new_arbitrary_role'])
def test_renderer_receives_opaque_context_for_any_role(monkeypatch, scope, kind):
    received = []

    class Renderer:
        def paint(self, **context):
            received.append(context)

    monkeypatch.setattr(template_extension_registry, '_extensions', {})
    template_extension_registry.register(PageTemplateExtension(
        template_id='context-probe', widget_renderer=Renderer(), photo_scope=scope,
    ))
    instance = PageInstance(template_id='context-probe', settings={'unknown': {'value': 17}})
    composition = SimpleNamespace(
        page=SimpleNamespace(kind=kind, template_id=instance.template_id,
                             page_instance=instance, photos=('page-photo',)),
        photo_slots=(), page_number=None,
    )
    shared = {'arbitrary-pack': {'unknown-option': [1, 2]}}
    PageRenderer(translator=Translator('en')).paint(
        composition=composition, painter=None, target_rect=None, width=100, height=200,
        page_width_mm=100, page_height_mm=200, font_pixel_size=None, pixel_rect=None,
        thumbnail_cache=None, project_photos=('album-photo',), template_pack_settings=shared,
    )
    assert len(received) == 1
    context = received[0]
    assert context['instance'] is instance
    assert context['template_pack_settings'] is shared
    assert context['composition'] is composition
    assert context['photos'] == (('album-photo',) if scope == 'album' else ('page-photo',))
    assert context['project_photos'] == ('album-photo',)
