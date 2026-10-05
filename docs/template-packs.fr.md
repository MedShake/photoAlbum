# Ajouter un pack de templates

[English](template-packs.md) | **Français**

MSB reste le pack intégré et la sélection par défaut. Des packs supplémentaires peuvent être ajoutés sous `src/photoalbum/templates/` sans modifier le moteur, l’interface ni la configuration de packaging. Un album peut mélanger des templates provenant de plusieurs packs. Les templates sont des modules Python exécutables, et non des fichiers HTML ou Jinja.

## Structure

```text
src/photoalbum/templates/my_pack/
    __init__.py
    manifest.json
    photo/
        __init__.py
        layout.py
        widget_renderer.py
        settings.py
    assets/                 # optionnel ; peut contenir des sous-dossiers
    screenshots/            # optionnel
    i18n/en.json            # catalogue optionnel du pack
    docs/help.html          # documentation optionnelle du pack
    README.md               # optionnel
```

Le nom du dossier doit correspondre à l’`id` du manifest. Les modules Python référencés doivent être importables ; l’ID n’est pas utilisé pour construire les imports. Les IDs de templates doivent être uniques entre tous les packs ; les préfixer par le nom du pack évite les collisions.

```json
{
  "schema_version": 1,
  "id": "my_pack",
  "name": "My pack",
  "version": "1.0",
  "templates": [{
    "id": "my-pack-photo",
    "name": "One photo",
    "module": "photoalbum.templates.my_pack.photo",
    "kinds": ["photo_page"],
    "photo_capacity": 1
  }]
}
```

`schema_version` identifie la version du format du manifest ; `version` identifie la version du pack. Les métadonnées comprennent également `authors` (noms ou objets contenant un champ `name`) et une `description` optionnelle. Ces valeurs sont conservées lors de la découverte, indépendamment de leur affichage actuel dans l’interface.

Un pack peut ne fournir que certains types de pages, MSB fournissant les autres. Les types disponibles sont `photo_page`, `cover`, `special_page`, `body_special_page`, `day_divider`, `month_divider` et `year_divider`. Pour les couvertures, `cover_positions` peut contenir `front`, `inside_front`, `inside_back` et `back`.

## Compatibilité physique des pages

L’hôte possède les formats de papier nommés et l’orientation. Il convertit ces choix en largeur et hauteur physiques avant de demander la compatibilité d’un template. Les templates ne déclarent donc pas de liste blanche de formats ou d’orientations.

Un template peut déclarer dans le manifest des limites physiques optionnelles via `page_constraints`, par exemple `min_width_mm`, `max_width_mm`, `min_height_mm` et `max_height_mm`. L’absence de limite signifie qu’aucune restriction géométrique n’est imposée par le manifest. Les restrictions de type de page et de position de couverture continuent de s’appliquer indépendamment.

La commande CLI de catalogue expose ces informations collectées ; le format JSON permet également de les exploiter de manière structurée.

## API publique d’écriture des packs

Le rôle opt-in `body_special_page` autorise une occurrence au milieu du corps
depuis le Plan. Il n’est pas impliqué par `special_page`. MSB `dedication` et
`blank`, ainsi que Simplex `simplex-full-photo-cover`, le déclarent. Le format
du manifeste reste en version 1 ; seul l’ensemble de valeurs de rôle s’étend.
Ces pages utilisent le renderer habituel et reçoivent le contexte temporel de
leur ancrage. Voir [la pagination éditoriale](editorial-pagination.md).

Les packs doivent importer les primitives de l’hôte depuis `photoalbum.template_engine.api` plutôt que depuis les modules internes :

```python
from photoalbum.template_engine.api import (
    PageInstance, PageTemplateExtension, register_template_extension,
    NormalizedRect, PageComposition, PhotoSlotComposition, TemplateLayout,
    PageComposer, PreviewJob, TemplatePreviewBackend, PageTemplateSettingsWidget,
)
```

Cette façade expose les modèles génériques d’instances et de pages, les primitives de layout et de composition, le contrat du backend d’aperçu et la classe de base des éditeurs de réglages. Les auteurs de packs n’ont pas à dépendre de modules internes comme `album.composition`, `preview_backend` ou `gui.template_settings.base`. Les exports sont les vrais types de l’hôte : il n’existe ni wrapper de compatibilité ni implémentation spécifique à un pack dans cette API.

L’hôte possède `PreviewRenderService`. Lorsqu’un éditeur est créé isolément sans service, `PageTemplateSettingsWidget` en fournit un appartenant au widget. Un pack ne doit pas construire lui-même `PreviewRenderService`. En revanche, les workers réalisant les calculs propres à l’aperçu d’un pack restent dans ce pack.

## Enregistrer le comportement

Le champ `module` du manifest est un nom absolu de module Python importable. Il n’est jamais déduit de l’ID du pack ni de son dossier. La découverte du catalogue n’importe aucun code Python.

Chaque module déclaré expose `register()`. Les imports Qt d’éditeur peuvent rester à l’intérieur de cette fonction afin que la découverte du catalogue et des layouts ne crée pas de widgets.

```python
from photoalbum.template_engine.api import (
    PageTemplateExtension, register_template_extension,
)


def validate(settings):
    if not isinstance(settings.get("density"), int):
        raise ValueError("density must be an integer")


def register():
    from .widget_renderer import PhotoRenderer
    from .settings import PhotoSettingsWidget

    register_template_extension(PageTemplateExtension(
        template_id="my-pack-photo",
        widget_renderer=PhotoRenderer(),
        settings_editor_type=PhotoSettingsWidget,
        settings_defaults=lambda: {"density": 17},
        validate_settings=validate,
        photo_scope="page",  # ou "album"
    ))


def register_layouts(registry):
    from .layout import PhotoLayout
    registry.register("my-pack-photo", PhotoLayout())
```

`register_layouts(registry)` est obligatoire pour les templates déclarant une capacité photo. D’autres templates peuvent aussi fournir un layout. Chaque layout implémente `compose(page, instance, page_numbers, *, page_width_mm, page_height_mm, reserved_caption_lines=None)` et renvoie une `PageComposition`. `instance.settings` reste opaque pour le moteur : le pack possède sa géométrie, la préparation du contenu et les règles de légendes.

Un layout peut optionnellement implémenter `required_caption_lines(...)` et `reserve_caption_lines(required)`. Le compositeur peut alors partager les mesures sur une double page et signaler les débordements ; le pack décide comment le texte est mesuré et combien d’espace est réservé.

Un module partagé par plusieurs templates n’est traité qu’une fois par passe d’enregistrement et doit donc enregistrer tous leurs IDs. L’absence d’un layout obligatoire produit une erreur identifiant le template. Une occurrence isolée peut utiliser `PageComposer.compose_instance(instance, photos, ...)`, y compris hors pagination normale, ce qui permet à un layout optionnel de fonctionner aussi sur une couverture.

## Rendu et réglages

`PageRenderer.paint_template()` est le point de dispatch unique de tous les renderers de templates : aperçus de réglages, pages paginées, couvertures et PDF. Il n’existe pas de branche de dispatch fondée sur l’ID d’un template ou son rôle dans l’album. Le wrapper `paint()` gère les numéros de page et l’affichage de secours pour les pages sans renderer.

Chaque `widget_renderer.paint()` reçoit le même contexte nommé : painter et rectangle cible, dimensions physiques, instance et réglages opaques, réglages du pack, photos, photos du projet, pages de l’album, composition, cache de miniatures, traducteur du pack, service de rendu et options d’affichage. Déclarez les arguments utilisés et acceptez `**kwargs` pour les autres.

Le PDF fournit `render_service=None` : un renderer doit donc aussi savoir rendre de manière synchrone. Un `TemplatePreviewBackend` optionnel peut fournir des travaux asynchrones coûteux via `PreviewJob` ; le métier reste dans le pack, l’hôte assurant l’ordonnancement et le cache.

`create_template_instance(template_id)` appelle la fabrique optionnelle de valeurs par défaut, copie son résultat puis exécute la validation optionnelle. La validation de l’album utilise le même callback avant composition/export. Charger des réglages préserve les valeurs enregistrées et ne les remplace jamais par de nouveaux défauts.

Les réglages locaux sont des dictionnaires compatibles JSON dans `PageInstance.settings`. Les réglages partagés sont dans `AlbumStructureSettings.template_pack_settings`, indexés par ID de pack. Leur signification, validation et interface appartiennent entièrement au pack.

Pour fournir un dialogue de réglages partagés, déclarez son point d’entrée dans le manifest :

```json
"settings_editor": "photoalbum.templates.my_pack.options:edit_settings"
```

Le callback reçoit les réglages, le traducteur et éventuellement le parent ; il renvoie un nouveau dictionnaire complet, `None` en cas d’annulation, et ne modifie pas les réglages reçus en place.

Un éditeur de template peut émettre le signal Qt `edit_theme_requested`. L’interface recherche alors le pack du template sélectionné et appelle ce hook. Sans déclaration, aucun dialogue de réglages de pack n’est ouvert.

## Découverte et activation

`discover_template_packs()` et `discover_templates()` sont en lecture seule : inspecter le catalogue local ne remplace pas les traductions, éditeurs ou extensions actifs.

`register_discovered_template_extensions(packs)` active l’ensemble fourni — ou l’ensemble intégré découvert s’il est omis — en remplaçant traductions, métadonnées d’éditeur et extensions exécutables. Les packs supprimés ne laissent aucun comportement enregistré. L’enregistrement est collecté avant publication : module ou `register()` manquant, extension dupliquée ou ID non déclaré laisse l’ensemble actif précédent intact. Les effets de bord des imports Python ne sont pas annulés.

`replace_active_template_packs(packs)` active uniquement métadonnées et catalogues et efface les extensions précédentes ; utilisez la fonction d’enregistrement lorsque le comportement exécutable est nécessaire. Un éditeur est importé paresseusement lorsqu’il est demandé. Un éditeur déclaré mais invalide provoque une erreur.

Les layouts utilisent les mêmes modules déclarés mais restent locaux au registre de chaque compositeur. Les compositeurs existants conservent leurs layouts : créez-en un nouveau après modification de l’ensemble installé. Découverte, chargement des layouts et activation des métadonnées n’importent pas un éditeur uniquement parce qu’il figure dans le manifest.

L’application ne déclare que `DEFAULT_TEMPLATE_PACK = "msb"`. L’objet optionnel `default_templates` du pack sélectionné associe les rôles d’album à ses propres IDs : `front_cover`, `inside_front_cover`, `inside_back_cover`, `back_cover`, `photo_page`, `year_divider`, `month_divider`, `day_divider`. Ces huit rôles sont obligatoires pour le pack par défaut et validés selon les usages autorisés des templates ; ils ne sont pas exigés des autres packs.

## Séparateurs de jour

`day_divider` est un rôle de séparateur ordinaire avec son propre template et sa `PageInstance`. Ses éléments planifiés et pages rendues portent `year`, `month` et `day`, accessibles au renderer via `composition.page`. Un pack fournissant ce rôle le déclare comme les autres séparateurs et peut le choisir dans `default_templates`.

## Contexte temporel et dates localisées

Les renderers peuvent recevoir `temporal_context`, qui indique les niveaux de séparateurs d’année et de mois réellement matérialisés pour la période rendue. Il décrit uniquement la structure de l’album ; chaque pack décide de son effet sur la présentation.

L’API publique fournit `format_date_parts(date, language=..., weekday=..., day=..., month=..., year=...)` pour les titres de dates localisés. Elle gère noms localisés, ordre des composants, ponctuation et détails propres à la langue comme le français `1er`, indépendamment de la locale système. Les langues actuellement prises en charge sont l’anglais et le français, variantes régionales comprises.

## Traductions et ressources

Placez les catalogues dans `i18n/<language>.json`. Le fallback suit cet ordre : langue sélectionnée dans le pack, anglais du pack, catalogue de l’application, puis clé elle-même. Renderers, éditeurs, libellés et aperçus asynchrones utilisent ce routage, y compris pour les couvertures PDF. Un pack n’utilise jamais le catalogue d’un autre pack ; les catalogues globaux contiennent le texte de l’application.

Déclarez `documentation` comme chemin relatif ou comme mapping langue/chemin. L’aide le découvre génériquement ; l’absence d’un fichier localisé retombe sur l’anglais. Les assets vivent sous le dossier du pack et peuvent être résolus relativement aux modules Python du pack. Aucun registre central de ressources ou de documentation n’est nécessaire pour ajouter un pack.

## Packaging et vérification

Les manifests, `README.md`, `docs/*`, `i18n/*.json`, `screenshots/*` et `assets/` récursifs sont inclus automatiquement dans les distributions Python. PyInstaller collecte déjà les sous-modules et données de tous les packs. Un pack est ajouté aux sources ; une application déjà distribuée doit être reconstruite pour l’inclure.

Avant distribution, vérifiez découverte, composition, réglages, aperçu et export PDF. `tests/fixtures/template_packs/testpack/` constitue un exemple indépendant avec réglages opaques, éditeurs, renderer, layout, aperçu asynchrone, catalogues, asset et documentation. Le test de cycle de vie copie uniquement ce dossier dans un arbre source, exerce interface, persistance et export, puis retire physiquement les packs. Le test de distribution l’ajoute également avant de construire sdist et wheel, installe le wheel et rejoue le même cycle hors du checkout.
