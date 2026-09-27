# Architecture de l’interface graphique

[English](gui-architecture.md) | **Français**

`MainWindow` coordonne le projet ouvert, les onglets du flux de travail, la construction de l’album et la synchronisation des vues. Les modifications des lieux et des légendes sont enregistrées immédiatement ; l’album est reconstruit lorsque l’utilisateur quitte cet onglet, ou avant l’export PDF.

Les composants suivants possèdent leur état et leurs responsabilités :

- `PhotoSourcesWidget` : choix du dossier source, modèles de tableaux, tri, sélection, journal et aperçus au survol. Les actions utilisateur sont émises sous forme de signaux ; ce widget ne connaît pas `MainWindow`.
- `ScanController` : démarrage et annulation de l’analyse, thread de travail, progression et compte rendu dans le widget source. Il informe la fenêtre lorsque des photos deviennent disponibles ou que l’état de l’analyse change.
- `PhotoEditor` : boîtes de dialogue de date et GPS, persistance via `ProjectService`, géocodage et ouverture des images. Il émet les erreurs, messages de journal et demandes d’actualisation.
- `PdfExportWidget` : options PDF, validation, export en arrière-plan et progression. Il reçoit explicitement le service de projet et les callbacks permettant de lire les réglages, d’obtenir l’album et de préparer l’export.

Les composants reçoivent leurs dépendances par leur constructeur. Leur parent Qt gère leur durée de vie et le placement des dialogues ; il n’est jamais utilisé pour accéder aux champs privés de la fenêtre. Chaque propriétaire d’un thread conserve son worker jusqu’à la fin du thread, puis libère ses références et l’objet Qt.

Le format de papier et l’orientation appartiennent à l’hôte. Celui-ci les convertit en dimensions physiques avant de créer les éditeurs de réglages, aperçus et exports PDF. La compatibilité des templates repose sur les limites physiques optionnelles déclarées dans le manifest du pack. L’interface délègue cette décision au modèle central des templates à partir de ces dimensions, sans restriction de nom de format ou d’orientation dans les templates. Le rendu utilise les mêmes dimensions.

Le format personnalisé stocke directement largeur et hauteur en millimètres et ignore le sélecteur d’orientation. Le formulaire accepte des dimensions de 50 à 2000 mm avec deux décimales. Modifier ces champs ne notifie pas l’album ; **Appliquer** valide les deux dimensions et émet une seule modification consolidée. `AlbumStructureSettings.effective_page_format()` résout les formats nommés et personnalisés pour les aperçus, éditeurs de templates et exports PDF. Les dimensions personnalisées sont persistées dans le projet ; les anciens projets conservent le comportement des formats standards.

`PageTemplateSettingsWidget` fournit la mise en page commune des réglages : contrôles défilants à côté d’un titre et d’une page d’aperçu alignés en haut. Sa fabrique d’aperçu conserve le rapport physique de la page dans les limites de l’écran. `PageInstanceDialog` adapte sa taille à son contenu ; les templates fournissent leurs contrôles et leur rendu sans reconstruire la colonne d’aperçu.

Les changements de format et d’orientation actualisent les choix compatibles en une seule transaction de réglages. Le chargement des réglages n’émet aucun changement ; une action utilisateur en émet un après restauration ou remplacement de toutes les sélections dépendantes.

Les pages spéciales sélectionnées restent dans le projet lorsque leur template devient incompatible avec les dimensions courantes. Leur ligne affiche un avertissement et désactive le bouton de réglages. `AlbumBuilder` les filtre du plan effectif avant pagination : aperçus et PDF les omettent sans perdre l’ordre enregistré, les identifiants d’instance ni les options. Le retour à des dimensions compatibles les restaure automatiquement. Le préchauffage des aperçus utilise lui aussi le plan effectif.

Le cache asynchrone des aperçus inclut les dimensions physiques et en déduit le rapport du raster canonique. Le backend du pêle-mêle exclut le style du titre de la signature de son arrière-plan : modifier seulement le titre repeint la surcouche légère, tandis qu’un changement de graine ou de géométrie demande un nouvel arrière-plan.

`tests/test_main_window_components.py` vérifie les connexions entre composants, une vraie analyse d’un dossier temporaire, l’édition et la restauration des métadonnées, la sélection après tri et l’exécution des tâches en arrière-plan.
