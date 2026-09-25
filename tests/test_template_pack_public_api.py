import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.gui.preview_render_service import PreviewRenderService
from photoalbum.gui.template_settings import create_template_settings_editor
from photoalbum.i18n import Translator
from photoalbum.template_engine import register_discovered_template_extensions
from photoalbum.template_engine.api import PageInstance, PageTemplateSettingsWidget


@pytest.mark.parametrize('inject_service', [False, True])
def test_host_supplies_preview_service_to_pack_editor(inject_service):
    app = QApplication.instance() or QApplication([])
    register_discovered_template_extensions()
    service = PreviewRenderService(Translator('en')) if inject_service else None
    editor = create_template_settings_editor(
        'year-photo-scatter', PageInstance(template_id='year-photo-scatter'), (),
        translator=Translator('en'), render_service=service,
    )
    assert isinstance(editor, PageTemplateSettingsWidget)
    assert isinstance(editor._render_service, PreviewRenderService)
    assert editor._shared_render_service is editor._render_service
    if inject_service:
        assert editor._render_service is service
    else:
        assert editor._render_service.parent() is editor
    editor.close()
    app.processEvents()


def test_example_pack_uses_only_public_authoring_imports():
    fixture = Path(__file__).parent / 'fixtures/template_packs/testpack'
    for path in fixture.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('photoalbum.'):
                assert node.module == 'photoalbum.template_engine.api', path
    settings = Path('src/photoalbum/templates/msb/year_photo_scatter/settings.py').read_text()
    assert 'PreviewRenderService' not in settings
