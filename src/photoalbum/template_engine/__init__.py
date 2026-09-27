from photoalbum.template_engine.extensions import PageTemplateExtension, register_template_extension, template_extension_registry
from photoalbum.template_engine.discovery import TemplatePack, create_template_registry, discover_template_packs, discover_templates, load_template_pack, register_discovered_template_extensions, replace_active_template_packs
from photoalbum.template_engine.translations import translator_for_template

from photoalbum.template_engine.instances import create_template_instance

__all__ = [
    "create_template_instance",
    "PageTemplateExtension",
    "TemplatePack",
    "create_template_registry",
    "discover_template_packs",
    "discover_templates",
    "load_template_pack",
    "register_discovered_template_extensions",
    "replace_active_template_packs",
    "register_template_extension",
    "template_extension_registry",
    "translator_for_template",
]
