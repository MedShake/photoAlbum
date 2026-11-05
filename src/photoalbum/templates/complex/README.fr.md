# Complex 1.4.0 — Photo Album 0.4.1

Pack **indépendant de MSB** : aucune dépendance vers le pack MSB à l'exécution.

## Templates conservés

Un template par capacité (`complex-photo-1` ... `complex-photo-5`), avec un seul mode automatique `complex-auto-1-5`.

- 1 à 3 photos : fonctionnement inchangé depuis 1.3.0.
- **4 photos — Reportage** : **géométries strictement inchangées** depuis 1.3.0 (4 variantes A4 portrait, 4 A4 paysage, 2 carré). Les doublons de signature en paysage bénéficient désormais de l'alternance automatique.
- **5 photos — Mosaïque / Séquence** : les variantes de chaque famille et de chaque format sont réunies dans le menu du même template `complex-photo-5`.

| Format | Mosaïque | Séquence | Total variantes 5 photos |
|---|---:|---:|---:|
| A4 portrait | 6 (colonne double PP et triple P/L/L, de chaque côté) | 3 (grande en haut, au centre ou en bas) | **9** |
| A4 paysage | 6 (permutations des colonnes PP, P, LL) | 2 (deux grandes en haut ou en bas) | **8** |
| Carré | 12 (3 photos en haut / 2 en bas ou l'inverse, avec PPL et PL) | **Aucune** | **12** |

**Total : 29 dispositions de 5 photos.** Les ratios des cellules sont 3:4 (portrait) et 4:3 (paysage), avec `ImageFit.CONTAIN`, sans recadrage. Les légendes conservent leurs réglages (date, lieu, texte libre), avec les réserves de bande et l'adaptation du texte existantes.

## Chronologie

- A4 portrait Mosaïque : on lit les colonnes de gauche à droite, chaque colonne de haut en bas.
- A4 paysage Mosaïque : on lit les colonnes de gauche à droite (PP, P et LL), chaque colonne de haut en bas.
- Carré Mosaïque : on lit les rangées de haut en bas, **de gauche à droite** au sein de chaque rangée.
- Séquence : de gauche à droite dans la rangée supérieure, puis les rangées suivantes.
- Reportage conserve ses règles spécifiques 1.3.0, y compris portrait à droite = photo 1 sur page paysage, portrait à gauche = photo 4 sur page paysage.

Les listes de cellules dans `photo_page/geometry.json` sont **dans l'ordre chronologique des photos** et alimentent aussi les signatures automatiques. Jamais de permutation arbitraire des fichiers pour rendre un modèle compatible.

## Mode automatique et rotation

L'algorithme privilégie, pour les photos admissibles de la page en cours, **5, puis 4, puis 3, puis 2, puis 1** photo. Il ne franchit pas les limites éditoriales imposées par la pagination (périodes, insertions, pages manuelles). Il ne recadre ni ne réordonne les photos.

Si plusieurs dispositions de même capacité conviennent à la signature chronologique, elles tournent **dans leur ordre de déclaration** : première occurrence automatique → première variante, deuxième occurrence automatique → deuxième variante, etc. Les compteurs sont indépendants pour chaque paire `(format de page, signature P/L)`.

**Une page manuelle ne fait jamais avancer les compteurs.** Les comptes ne sont incrémentés que quand la sélection automatique est réellement appelée pour une page retenue ; à chaque pagination complète, ils sont réinitialisés. Aucun état global caché, aucun `random()` non reproductible : même album et mêmes paramètres → choix identiques.

**Intégration nécessaire :** l'API d'origine Photo Album 0.4.1 ne fournit pas de compteur de pagination aux packs. Il faut également appliquer le mini-correctif hôte (fichiers `album/templates.py` et `album/pagination.py`) fourni dans l'**archive complète**. Sans cet ajout, le pack fonctionne encore, mais choisit toujours la première variante compatible au lieu de faire tourner les choix.

## Installation dans Photo Album 0.4.1

### Recommandé : archive complète

Extraire `Complex_installation_complete_PhotoAlbum_0.4.1_v1.4.0.zip` **à la racine du projet `photoAlbum-main/`**, en remplaçant les fichiers fournis :

- `src/photoalbum/templates/complex/` (supprimer d'abord la version antérieure) ;
- `src/photoalbum/album/templates.py` (ajout facultatif rétrocompatible au contexte automatique) ;
- `src/photoalbum/album/pagination.py` (compteurs ne vivant que pendant une pagination).

Faire une sauvegarde préalable si ces deux fichiers hôtes ont été modifiés localement. La modification des deux fichiers hôtes est aussi fournie sous forme de diff pour examen / application manuelle.

### Pack seul

`Complex_pack_PhotoAlbum_0.4.1_v1.4.0.zip` ne contient que `complex/`, à mettre dans `src/photoalbum/templates/`. Pour activer la rotation des variantes, installer également le correctif hôte décrit ci-dessus.

Les identifiants historiques du modèle 4 sont inchangés. Les identifiants `five-mosaic-left` et `five-mosaic-right` sont conservés, mais leur ordre chronologique de cellules a été rectifié ; `five-sequence-center` reste proposé en portrait, et n'est plus proposé en paysage, conformément au schéma validé.

## Vérification

```bash
python src/photoalbum/templates/complex/qa/validate_geometry.py
QT_QPA_PLATFORM=offscreen python -m pytest -q src/photoalbum/templates/complex/qa
```

Tests automatisés Qt-indépendants : 39 géométries 4/5 photos, 29 variantes de 5, signatures et rotation, pages manuelles intercalées et régénération. **L'éditeur PySide6 et le rendu/export PDF doivent encore être vérifiés sur la machine Linux cible.**

Licence : GPL-3.0-or-later.
