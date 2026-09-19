from photoalbum.template_engine.extensions import (
    PageTemplateExtension,
    PageTemplateExtensionRegistry,
    register_template_extension,
    template_extension_registry,
)
from photoalbum.template_engine.discovery import (
    DiscoveredTemplates,
    TemplatePack,
    create_template_registry,
    discover_template_packs,
    discover_templates,
    load_template_pack,
    register_discovered_template_extensions,
    register_discovered_layouts,
)


__all__ = [
    "DiscoveredTemplates",
    "PageTemplateExtension",
    "PageTemplateExtensionRegistry",
    "TemplatePack",
    "create_template_registry",
    "discover_template_packs",
    "discover_templates",
    "load_template_pack",
    "register_discovered_template_extensions",
    "register_discovered_layouts",
    "register_template_extension",
    "template_extension_registry",
]
