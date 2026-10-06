# Pack de templates Simplex

[English](developer.md) | **Français**

Le pack **Simplex** contient volontairement des templates de page minimaux.

Son template, `simplex-full-photo-cover`, est un template photographique pleine page utilisable comme couverture ou comme page spéciale.

## Photo pleine page

Le template est disponible comme **page spéciale**, y compris dans le corps de l’album, et aux quatre positions de couverture : première de couverture, intérieur de première, intérieur de quatrième et quatrième de couverture.

Il ne déclare aucune limite géométrique. L’hôte fournit la largeur et la hauteur physiques de la page ; les formats nommés et orientations ne restreignent pas sa compatibilité.

L’image remplit toute la page sans marge. Son rapport d’aspect est conservé. Lorsque les rapports de l’image et de la page diffèrent, l’image est agrandie pour couvrir la page et l’excédent est rogné symétriquement.

## Sources d’image

La page accepte deux modes de source.

### Photo du projet

Le sélecteur utilise les photos actives disponibles pour les templates, identifiées par `source_id + asset_id`. Choisir une photo ne change pas son utilisation : une photo `BODY` reste dans le corps ; une photo `TEMPLATE_ONLY` reste réservée aux templates ; une photo `OFF` n’est pas proposée.

### Fichier externe

Une image peut aussi être choisie directement dans le système de fichiers. Elle est utilisée sans être ajoutée à la collection de photos du projet.

Comme pour le modèle existant des photos sources, le projet conserve une référence vers le chemin du fichier. Déplacer ou supprimer ce fichier peut donc rendre l’image indisponible.

## Titre

Le titre facultatif est automatique ou personnalisé en Markdown (gras et italique). Le titre automatique décrit la période du jeu de photos datées fourni au template : mois et année, année, ou plage d’années. Les réglages permettent de masquer le titre et de choisir sa position verticale, sa police, sa taille et sa couleur.

## Interface de réglages

Les réglages suivent la convention commune en deux colonnes :

- réglages et choix de la source à gauche ;
- aperçu en direct à droite.

Changer la photo du projet, le mode de source ou le fichier externe actualise immédiatement l’aperçu.

## Intégration au système de packs

Simplex est découvert par le mécanisme standard des packs de templates. Son comportement exécutable est enregistré comme extension de template, et non par une branche spécifique à Simplex dans l’interface principale.

Les choix de couverture sont filtrés selon la position déclarée et selon les éventuelles limites physiques déclarées par le template. Ce template ne déclare aucune limite géométrique.

Voir [Créer des packs](https://github.com/MedShake/photoAlbum/wiki/Template-packs-fr) pour les contrats communs et [Développement](https://github.com/MedShake/photoAlbum/wiki/Development-fr) pour les responsabilités de l’interface.
