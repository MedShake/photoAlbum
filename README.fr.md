# Photo Album

**L’application pour ceux qui ne font jamais d’albums… et ceux qui aiment savoir où leurs photos ont été prises !**

[English](README.md) | **Français**

Photo Album est une application créée par **Bertrand Boutillier** pour réaliser simplement des albums photo à partir de ses propres images, avec une attention particulière portée aux dates, aux lieux et aux légendes.

Elle est née autour de deux idées principales : exploiter réellement les informations géographiques contenues dans les photos grâce à une **géolocalisation inverse intégrée**, et proposer un **moteur de templates extensible** permettant de construire différents types d’albums sans enfermer l’application dans une mise en page unique.

Pensée pour être très modulaire, elle propose aujourd’hui les modèles d’album que son auteur utilise lui-même — descendants directs de ceux qu’il fabriquait autrefois avec quelques bouts de PHP et pas mal de bricolage maison.

Après quelques décennies à faire du Web, il était peut-être temps d’en faire une vraie application. C’est désormais chose faite, avec l’aide de l’IA.

---

## Testez rapidement les capacités du logiciel !

Pour découvrir ce que Photo Album peut réellement apporter, le mieux est de l’essayer directement avec **un ensemble représentatif de vos propres photos**.

N’hésitez pas à rassembler dans un dossier **quelques centaines de photos originales couvrant une ou deux années**, idéalement incluant leurs **dates de prise de vue EXIF** et leurs **coordonnées GPS**. Utilisez ensuite simplement ce dossier comme source dans Photo Album et lancez l’analyse.

Avec un tel ensemble, l’application peut réellement exploiter la chronologie des photos, leur répartition géographique et les changements de lieux au fil du temps. La géolocalisation inverse et la construction automatique de l’album prennent alors tout leur sens.

À l’inverse, un essai avec moins d’une cinquantaine de photos, prises à des dates très éparses ou dans des lieux sans véritable continuité entre eux, donnera naturellement un résultat moins représentatif — et probablement moins séduisant — des possibilités du logiciel.

Pour un premier essai, **prenez donc beaucoup de vraies photos plutôt qu’un petit échantillon soigneusement sélectionné** : Photo Album est justement conçu pour faire le travail à partir d’une collection conséquente.

## Pourquoi Photo Album ?

Faire un album photo paraît simple jusqu’au moment où il faut réellement trier les images, vérifier leurs dates, retrouver où elles ont été prises, écrire les légendes, choisir leur disposition et maintenir une présentation cohérente sur plusieurs dizaines de pages.

Photo Album cherche à automatiser ce qui peut l’être sans retirer à l’utilisateur le contrôle éditorial sur son album.

L’application analyse les photos et leurs métadonnées, aide à exploiter leurs informations géographiques, permet de corriger et d’organiser les informations obtenues, puis utilise des templates pour construire et générer l’album.

L’objectif n’est donc pas seulement de « mettre des photos dans un PDF », mais de disposer d’un outil permettant de construire progressivement un album cohérent à partir d’une collection de photos.

## Points forts

### Géolocalisation inverse intégrée

Les coordonnées GPS enregistrées par les appareils photo et les smartphones sont utiles à une machine, mais peu agréables dans un album.

Photo Album intègre un système de **reverse geocoding** permettant de transformer ces coordonnées en informations géographiques compréhensibles.

Une position peut contenir plusieurs niveaux d’information : lieu remarquable, route, quartier, hameau, village, ville, région, pays, etc. Photo Album conserve cette richesse au lieu de réduire immédiatement une position à un simple nom de ville.

L’utilisateur peut ensuite choisir les composants géographiques réellement pertinents pour son album, les activer ou les désactiver et corriger les résultats lorsque cela est nécessaire.

Une édition groupée permet également d’appliquer efficacement des corrections à plusieurs photos partageant les mêmes informations géographiques.

Le but est de passer de simples coordonnées GPS à une **information de lieu utile pour une légende d’album**, tout en conservant le contrôle humain sur le résultat final.

### Moteur de templates extensible

Photo Album est conçu autour d’un **moteur de templates modulaire**.

La mise en page d’un album n’est donc pas enfermée dans une composition unique codée directement dans l’application. Les templates définissent les différentes dispositions disponibles et permettent de faire évoluer les possibilités de mise en page sans reconstruire tout le logiciel.

Les templates actuellement fournis correspondent aux modèles utilisés par l’auteur pour ses propres albums. Ils sont les descendants de mises en page autrefois produites à l’aide de scripts PHP maison.

L’objectif de l’architecture est de permettre l’ajout progressif de nouveaux modèles et, à terme, de faciliter la création de collections de templates adaptées à différents types d’albums.

## Fonctionnalités

Photo Album permet notamment de :

- créer et ouvrir des projets d’album ;
- analyser un dossier de photos ;
- lire les métadonnées utiles des images ;
- exploiter les dates de prise de vue ;
- détecter les coordonnées GPS disponibles ;
- effectuer une géolocalisation inverse ;
- conserver les différents composants d’un lieu ;
- sélectionner les informations géographiques pertinentes pour les légendes ;
- corriger individuellement ou par lot les informations de lieu ;
- ajouter et modifier les légendes des photos ;
- organiser les photos et les pages de l’album ;
- utiliser différents templates de mise en page ;
- prévisualiser l’album ;
- générer le document final au format PDF.

L’interface est disponible en français et en anglais.

## Organisation générale de l’application

Le travail sur un album suit plusieurs étapes accessibles depuis l’interface.

### Photos

Cette partie permet d’importer et d’analyser les photos qui serviront à l’album.

Les métadonnées disponibles sont examinées afin de récupérer notamment les dates de prise de vue et les éventuelles coordonnées GPS.

### Lieux et légendes

Cette étape permet de contrôler les informations éditoriales associées aux photos.

Les résultats de la géolocalisation peuvent être examinés et ajustés. Les différents composants d’un lieu peuvent être activés ou désactivés afin de construire une indication géographique adaptée à l’album.

Les modifications groupées facilitent les corrections lorsque plusieurs photos partagent le même contexte géographique.

Les légendes peuvent également être préparées et modifiées ici.

### Album

Cette partie définit les paramètres généraux et la mise en forme de l’album.

Elle permet tout d’abord de choisir le **format du papier** et son **orientation**.

La composition repose ensuite sur le moteur de templates de Photo Album. Des templates peuvent être sélectionnés pour les différentes familles de pages qui constituent un album :

- les quatre pages de couverture ;
- les pages de transition entre les mois ou les années ;
- les pages contenant les photos ;
- les pages spécifiques pouvant être ajoutées à l’album.

Cette organisation permet de faire évoluer l’apparence et la structure d’un album en changeant ses templates plutôt qu’en modifiant le moteur de rendu lui-même.

Il est également possible de demander à Photo Album de contraindre le nombre total de pages à un **multiple de 4**, afin de tenir compte des contraintes courantes de fabrication et d’impression des albums.

### Plan

Le plan donne une **vue d’ensemble de la structure de l’album** telle qu’elle résulte des photos, des paramètres et des templates sélectionnés.

Il ne sert pas à organiser manuellement les pages : il permet au contraire de comprendre la composition obtenue et d’identifier les éventuels ajustements à effectuer.

Photo Album peut notamment y signaler des **emplacements photo non occupés** et fournir des **conseils sur les pages qu’il pourrait être utile d’ajouter** pour obtenir une composition plus cohérente.

Le plan constitue ainsi une étape de contrôle entre la configuration de l’album et son rendu visuel.

### Aperçu

L’aperçu fournit une représentation **WYSIWYG** (*What You See Is What You Get*) de l’album.

Il permet de parcourir visuellement les pages telles qu’elles seront rendues, avec leurs photos, leurs légendes, leurs informations de lieu et la mise en page définie par les templates.

Cette étape permet de contrôler le résultat réel de la composition avant de générer le document définitif.

### Export PDF

La dernière étape génère le **document PDF final** correspondant à l’album préparé et contrôlé dans l’aperçu.

Photo Album permet de choisir la **qualité du PDF généré**, afin d’adapter le document final à son usage.

## Philosophie du projet

Photo Album essaie de conserver une séparation claire entre :

- les **photos originales** ;
- les **métadonnées extraites** ;
- les **choix éditoriaux de l’utilisateur** ;
- la **composition de l’album** ;
- le **rendu final**.

Cette séparation permet de corriger ou de réorganiser un album sans avoir à altérer les fichiers photo originaux.

Le projet privilégie également une architecture modulaire. Les fonctionnalités liées aux métadonnées, à la géolocalisation, à la composition et au rendu sont conçues comme des responsabilités distinctes plutôt que comme un unique bloc de traitement.

## Architecture

Le code source principal se trouve dans :

    src/photoalbum/

Le projet est organisé en différents composants responsables notamment :

- de l’accès aux données du projet ;
- de l’analyse des photos et de leurs métadonnées ;
- de la géolocalisation ;
- de l’interface graphique ;
- de la construction des légendes de lieu ;
- de la composition des pages ;
- des templates ;
- du rendu et de l’export PDF ;
- de l’internationalisation.

Cette organisation doit permettre de faire évoluer chaque partie sans rendre les templates ou l’interface dépendants des détails internes des autres composants.

## Développement

Photo Album est développé en **Python**.

L’interface graphique utilise **Qt via PySide6**.

Le projet dispose également d’une suite de tests automatisés avec **pytest**.

Pour lancer les tests depuis un environnement de développement configuré :

    pytest -q

Le projet fournit notamment la commande :

    pa

pour lancer l’application graphique depuis l’environnement Python dans lequel Photo Album est installé.

Une documentation plus détaillée sur l’installation et l’environnement de développement sera ajoutée au fur et à mesure de la stabilisation du projet.

## Internationalisation

Photo Album dispose actuellement d’une interface en :

- français ;
- anglais.

Par défaut, l’application choisit sa langue à partir de l’environnement du système, avec l’anglais comme langue de repli.

La langue de l’interface peut également être forcée au lancement pour faciliter les tests et l’utilisation dans un environnement multilingue.

## État du projet

Photo Album est un projet personnel en développement actif.

Il est déjà utilisé pour produire de véritables albums, mais son architecture et son interface continuent d’évoluer.

Les templates fournis correspondent d’abord aux besoins réels de l’auteur. Le moteur est cependant conçu pour pouvoir accueillir progressivement d’autres modèles et d’autres usages.

## Contributions

Les retours, rapports de bugs et propositions d’amélioration sont les bienvenus.

Une attention particulière est portée à la conservation d’une architecture lisible et modulaire, notamment pour tout ce qui concerne :

- le moteur de templates ;
- la géolocalisation et les lieux ;
- la composition des albums ;
- l’interface utilisateur ;
- l’internationalisation.

## Licence

Photo Album est un logiciel libre distribué selon les termes de la **GNU General Public License, version 3 ou ultérieure (GPLv3+)**.

## Auteur

**Bertrand Boutillier**

b.boutillier@gmail.com

Photo Album est réalisé avec l’aide de l’IA par un type qui fait du Web depuis quelques décennies.

## Dédicace

*Dédié à mes deux filles adorées, **Petit-Gâteau et Sido**. ❤️*