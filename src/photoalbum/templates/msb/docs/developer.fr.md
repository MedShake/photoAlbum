# Pack de templates MSB

[English](developer.md) | **Français**

**MSB** est le pack de templates fourni avec Photo Album. Il contient les templates utilisés pour les couvertures, pages spéciales, séparateurs d’année, de mois et de jour, ainsi que les pages photo ordinaires.

Le pack est identifié par `msb`. Son catalogue est déclaré dans `src/photoalbum/templates/msb/manifest.json`. Le manifest est la source de vérité pour la disponibilité des templates, les types de pages pris en charge, les positions de couverture, les limites physiques optionnelles et les capacités photo.

## Compatibilité physique des pages

La plupart des templates MSB ne déclarent aucune limite géométrique. Le séparateur de mois classique exige au minimum 130 × 145 mm ; le calendrier annuel exige au minimum 180 × 180 mm. L’hôte fournit les dimensions physiques de page, orientation comprise. Les formats nommés ne restreignent pas la compatibilité. Les restrictions de type de page et de position de couverture continuent de s’appliquer.

Un album peut mélanger des templates MSB avec ceux d’autres packs installés.

## Catalogue des templates

| ID du template | Nom | Usages |
| --- | --- | --- |
| `year-photo-scatter` | Pêle-mêle annuel | Couverture, page spéciale |
| `geographic-word-cloud` | Nuage géographique | Couverture, page spéciale |
| `geographic-map` | Carte géographique | Couverture, page spéciale |
| `calendar-index` | Calendrier annuel | Couverture, page spéciale, séparateur d’année |
| `year-divider-classic` | Séparateur d’année simple | Séparateur d’année |
| `month-divider-classic` | Séparateur de mois avec liste de villes | Séparateur de mois |
| `month-divider-simple` | Séparateur de mois simple | Séparateur de mois |
| `day-divider-simple` | Séparateur de jour simple | Séparateur de jour |
| `photo-page-1` | Une photo | Page photo |
| `photo-page-2` | Deux photos | Page photo |
| `photo-page-3` | Trois photos | Page photo |
| `photo-page-4` | Quatre photos | Page photo |
| `dedication` | Dédicace | Page spéciale et page spéciale du corps, intérieur de première/intérieur de quatrième/quatrième de couverture |
| `blank` | Page blanche | Page spéciale et page spéciale du corps, intérieur de première/intérieur de quatrième/quatrième de couverture |

Les noms visibles par l’utilisateur sont traduits par Photo Album.

## Couvertures

Quatre templates MSB généraux sont utilisables aux quatre positions de couverture : `year-photo-scatter`, `geographic-word-cloud`, `geographic-map` et `calendar-index`.

Les positions possibles sont : première de couverture, intérieur de première, intérieur de quatrième et quatrième de couverture.

`dedication` et `blank` ont un rôle plus restreint : ils sont disponibles pour l’intérieur de première, l’intérieur de quatrième et la quatrième de couverture, mais pas pour la première de couverture.

Ces templates peuvent également servir de pages spéciales lorsque le manifest le déclare.

## Pêle-mêle annuel

`year-photo-scatter` crée une composition photographique à partir de toutes les photos datées fournies au template. Le template possède son code de composition, d’aperçu, de réglages et de rendu. Son backend d’aperçu filtre les photos fournies, ignore celles sans date de prise de vue et déduplique les identités `source_id + asset_id` avant de construire l’ensemble effectif.

Il peut être utilisé comme couverture ou page spéciale. Ses réglages sont locaux à l’instance de page, tandis que certains choix visuels communs peuvent hériter du thème MSB.

## Nuage géographique

`geographic-word-cloud` crée une composition géographique à partir des informations de localisation des photos du projet. Les réglages permettent de choisir l’année concernée et proposent une palette de douze couleurs mensuelles.

Par défaut, le template hérite des couleurs mensuelles du thème MSB. Une page peut définir sa propre palette puis supprimer cette surcharge pour revenir au thème du pack. Le template est utilisable comme couverture ou page spéciale.

## Carte géographique

`geographic-map` propose les projections Web Mercator, Equal Earth et Robinson. Le filtre annuel, les points, la palette mensuelle ou couleur unique et la légende sont propres à l’instance. La palette peut hériter du thème MSB.

L’aperçu utilise un calcul raster en arrière-plan ; le PDF peint la carte vectorielle directement. Les deux chemins partagent la préparation et la peinture. Voir [les coordonnées et le rendu](../geographic_map/README.md) pour les règles géographiques et [la provenance des données](../assets/geographic_map/README.md) pour Natural Earth.

## Calendrier annuel

`calendar-index` produit un calendrier/index annuel à partir des données de l’album. Il peut servir de couverture, de page spéciale ou de séparateur d’année.

Les réglages comprennent l’année affichée et l’affichage du titre. Lorsqu’il sert de séparateur d’année, l’année provient du contexte du séparateur et n’est pas librement choisie. Le renderer utilise la structure de l’album pour associer les mois aux numéros de pages correspondants.

## Séparateur d’année simple

`year-divider-classic` est le séparateur d’année classique de MSB. Ses réglages locaux comprennent la famille, la taille et la couleur de police du titre. Les valeurs de police par défaut peuvent hériter du thème MSB partagé.

L’éditeur suit la convention commune en deux colonnes : réglages à gauche, aperçu en direct à droite.

## Séparateur de mois avec liste de villes

`month-divider-classic` est le séparateur de mois détaillé. Il identifie le mois tout en présentant les informations géographiques de cette période, notamment la liste des villes. Son apparence participe au thème MSB commun et il possède ses propres réglages de page.

## Séparateur de jour simple

`day-divider-simple` affiche un titre de jour localisé avec la couleur du mois MSB et la police partagée, tout en proposant des réglages typographiques locaux. Il offre les formats jour de semaine/jour, jour de semaine/jour/mois et date complète. En mode Automatique, MSB adapte le titre aux niveaux de séparateurs de mois et d’année réellement matérialisés pour la période.

## Séparateur de mois simple

`month-divider-simple` est le séparateur de mois minimal de MSB. Il peut afficher le mois seul ou le mois et l’année. En mode Automatique, MSB omet l’année lorsqu’un séparateur d’année est matérialisé pour cette période.

Pour ces deux séparateurs simples, les règles automatiques sont des choix éditoriaux du pack MSB. Les formats manuels restent indépendants du contexte de l’album ; le formatage localisé des dates est fourni par l’hôte.

Le séparateur de mois simple hérite de la police MSB partagée sauf surcharge locale. Il convient lorsque le titre du mois suffit et que la liste de villes du séparateur classique n’est pas souhaitée.

## Pages photo

MSB fournit quatre mises en page photo ordinaires : `photo-page-1`, `photo-page-2`, `photo-page-3` et `photo-page-4`, avec des capacités respectives de 1, 2, 3 et 4 photos.

Les quatre templates partagent l’implémentation `photo_page` ainsi qu’un renderer et un éditeur de réglages communs, mais chaque ID possède sa propre disposition physique.

### Modes automatiques

`photo_page/automatic.py` possède les sélecteurs `msb-orientation-1-2` et `msb-orientation-1-2-3`. Ils utilisent les dimensions après correction de l’orientation EXIF et les dimensions physiques reçues. Le mode 1/2/3 est le choix par défaut du pack. Les règles de groupement sont décrites dans [le catalogue utilisateur](https://github.com/MedShake/photoAlbum/wiki/Templates-fr).

### Légendes

Les pages photo MSB prennent en charge trois sources : légende utilisateur, date/heure de prise de vue et localisation. Chaque composant peut être activé ou désactivé.

L’ordre par défaut est :

1. légende utilisateur ;
2. date/heure ;
3. saut de ligne ;
4. localisation.

Les éléments visibles sur une même ligne sont séparés typographiquement par un tiret cadratin. Le système prend aussi en charge des réglages de présentation locaux, notamment police et couleur.

Les dispositions MSB réservent l’espace des légendes dans la composition physique au lieu de les peindre par-dessus les photos. Les dispositions intégrées prennent en charge jusqu’à trois lignes de légende par photo.

## Dédicace

`dedication` fournit une page de texte dédiée. Il est déclaré comme page spéciale, page spéciale du corps et template de couverture, avec un usage de couverture limité à l’intérieur de première, l’intérieur de quatrième et la quatrième de couverture. Il reste donc absent des choix de première de couverture.

## Page blanche

`blank` est le template MSB le plus simple. Il crée une page volontairement vide et n’a aucune capacité photo. Il est disponible en page spéciale, en page spéciale du corps et aux trois positions de couverture autres que la première. Il sert aussi d’implémentation de référence minimale pour le contrat de rendu et de réglages d’un template.

## Thème MSB partagé

MSB possède des réglages au niveau du pack, partagés entre ses templates. Le thème contient actuellement une famille de police par défaut et une palette d’une couleur par mois.

Les réglages propres à une page restent dans son instance. Les réglages partagés restent dans `AlbumStructureSettings.template_pack_settings`, sous la clé `msb`. Une page peut ainsi hériter de l’apparence commune tout en conservant des surcharges locales lorsque le template le permet.

Par exemple, le nuage géographique peut hériter de la palette mensuelle ou stocker sa propre palette. Les éditeurs de templates peuvent demander l’éditeur du thème MSB via le mécanisme commun `edit_theme_requested`.

## Interface de réglages et aperçus

Les éditeurs MSB utilisent l’infrastructure commune des réglages de templates, selon une disposition en deux colonnes : contrôles à gauche, aperçu en direct à droite.

Modifier un réglage met à jour l’instance de page et actualise l’aperçu. Le même comportement exécutable du template sert aux aperçus de l’application et au rendu final ; un template doit donc rester rendu sans dépendre exclusivement d’un service d’aperçu asynchrone.

## Structure d’implémentation

Le paquet MSB contient une infrastructure partagée en plus des modules propres à chaque template. Parmi les modules importants :

- `settings_base.py` — comportement commun des éditeurs MSB ;
- `theme.py` — représentation du thème et gestion de la palette ;
- `theme_dialog.py` — éditeur des réglages de thème du pack ;
- `divider_style.py` — helpers typographiques des séparateurs ;
- `photo_page/layout.py` — dispositions physiques des quatre pages photo ;
- `photo_page/caption_layout.py` — calcul de l’espace des légendes ;
- `photo_page/caption_style.py` — visibilité, ordre et présentation des légendes.

Chaque module de template exécutable expose `register()` et enregistre un `PageTemplateExtension`. Les templates de pages photo enregistrent aussi leurs dispositions physiques. Les quatre IDs partageant un même module, celui-ci enregistre les quatre dispositions en une seule passe.

## Contrat de rendu

Les renderers de widgets sont utilisés à la fois pour l’aperçu GUI et l’export PDF. Selon le template, le rendu reçoit notamment l’instance de page, les photos du projet/effectives, les dimensions physiques, le rectangle cible en pixels, le traducteur, les pages de l’album, le cache de miniatures, la composition photo et les réglages MSB.

Le rendu PDF ne peut pas dépendre d’un service d’aperçu GUI asynchrone ; les renderers MSB doivent donc aussi savoir peindre immédiatement.

## Ajouter ou modifier des templates MSB

Le manifest fait autorité pour le catalogue. Ajouter un template nécessite généralement :

1. de le déclarer dans `manifest.json` ;
2. de fournir un module importable ;
3. d’enregistrer son extension exécutable ;
4. d’enregistrer une disposition lorsqu’il s’agit d’une `photo_page` ;
5. d’ajouter les noms visibles traduits ;
6. de couvrir découverte, réglages, aperçu, composition et export PDF par des tests.

Pour les contrats communs, voir [Créer des packs](https://github.com/MedShake/photoAlbum/wiki/Template-packs-fr) et [Développement](https://github.com/MedShake/photoAlbum/wiki/Development-fr).

### Dimensions minimales de page

Le séparateur de mois classique exige une largeur ≥ 130 mm et une hauteur ≥ 145 mm. Ces limites protègent la zone de titre et la zone des villes avec les marges prévues par la disposition intégrée.

Le calendrier annuel exige une largeur ≥ 180 mm et une hauteur ≥ 180 mm. Ce sont les limites déclarées par le manifest et imposées par l’hôte ; elles représentent la surface physique minimale attendue par la disposition de calendrier intégrée. Une typographie personnalisée ou un contenu exceptionnellement dense peut néanmoins nécessiter une page plus grande. Aucune limite n’est déclarée pour le pêle-mêle annuel.
