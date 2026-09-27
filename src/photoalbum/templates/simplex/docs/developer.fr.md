# Pack de templates Simplex

[English](developer.md) | **Français**

Le pack **Simplex** contient volontairement des templates de page minimaux.

Son premier template, `simplex-full-photo-cover`, est un template photographique pleine page utilisable comme couverture ou comme page spéciale.

## Photo pleine page

Le template est disponible comme **page spéciale** et aux quatre positions de couverture : première de couverture, intérieur de première, intérieur de quatrième et quatrième de couverture.

Il ne déclare aucune limite géométrique. L’hôte fournit la largeur et la hauteur physiques de la page ; les formats nommés et orientations ne restreignent pas sa compatibilité.

L’image remplit toute la page sans marge. Son rapport d’aspect est conservé. Lorsque les rapports de l’image et de la page diffèrent, l’image est agrandie pour couvrir la page et l’excédent est rogné symétriquement.

## Sources d’image

La page accepte deux modes de source.

### Photo du projet

Une photo déjà présente dans le projet peut être sélectionnée. Son utilisation ici ne la retire pas de l’album et ne la réserve pas exclusivement à cette page : elle reste disponible pour la composition normale de l’album.

### Fichier externe

Une image peut aussi être choisie directement dans le système de fichiers. Elle est utilisée sans être ajoutée à la collection de photos du projet.

Comme pour le modèle existant des photos sources, le projet conserve une référence vers le chemin du fichier. Déplacer ou supprimer ce fichier peut donc rendre l’image indisponible.

## Interface de réglages

Les réglages suivent la convention commune en deux colonnes :

- réglages et choix de la source à gauche ;
- aperçu en direct à droite.

Changer la photo du projet, le mode de source ou le fichier externe actualise immédiatement l’aperçu.

## Intégration au système de packs

Simplex est découvert par le mécanisme standard des packs de templates. Son comportement exécutable est enregistré comme extension de template, et non par une branche spécifique à Simplex dans l’interface principale.

Les choix de couverture sont filtrés selon la position déclarée et selon les éventuelles limites physiques déclarées par le template. Ce template ne déclare aucune limite géométrique.

Voir [`docs/template-packs.md`](../../../../../docs/template-packs.md) pour l’architecture générale des packs et [`docs/gui-architecture.md`](../../../../../docs/gui-architecture.md) pour les responsabilités de l’interface. Les versions françaises sont [`docs/template-packs.fr.md`](../../../../../docs/template-packs.fr.md) et [`docs/gui-architecture.fr.md`](../../../../../docs/gui-architecture.fr.md).
