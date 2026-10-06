# Sources de photos

Photo-Album considère une source comme une collection d’assets en lecture
seule. Une photo est identifiée par `source_id + asset_id` ; son `path` local
n’est que la représentation matérialisée utilisée par les renderers existants.

## Sémantique d’instantané

La sélection ou l’actualisation d’une collection crée un instantané explicite
dans le projet. Les changements de l’album distant restent sans effet jusqu’à
une synchronisation demandée par l’utilisateur. Cette actualisation :

- met à jour les métadonnées et valeurs d’origine du provider ;
- préserve dates, coordonnées, légendes et lieux éditoriaux manuels ;
- marque les assets disparus comme absents sans les supprimer ;
- ne change l’état absent que pour cette source, sans toucher aux autres.

## Plusieurs sources et utilisation des photos

La table ordonnée `sources` et `SourceRepository` constituent l’unique référence
de configuration. Chaque occurrence possède un UUID stable, son provider, sa
configuration non sensible, son activation et sa politique Date/GPS/Lieu/Nominatim.
Le scan récursif est propre à chaque source locale. Un ID ne détermine jamais le
type du provider ; plusieurs occurrences peuvent viser le même dossier/serveur.

L’onglet Photos comporte « Ajouter une source », « Source(s) de l’album » et
« Actualisation des photos ». Désactiver masque immédiatement les photos partout
en aval, sans perdre instantané ni corrections. Réactiver restaure cet instantané.
Supprimer demande confirmation et retire seulement cette source et ses photos
en base. Les sessions coexistent ; les traitements globaux parcourent les sources
actives séquentiellement et poursuivent après une erreur indépendante.
Reconnecter la même collection Synology via Modifier ne la resynchronise pas.

L’action d’utilisation propose trois choix explicites : dans le corps (`body`),
hors corps disponible aux modèles (`template_only`), désactivée (`off`). Cet état
survit aux rescans et ne remplace ni l’activation source ni l’état absent.
`list_photos()` inclut OFF pour les sources actives ; `list_album_photos()` exclut
OFF ; `list_body_photos()` ne conserve que BODY. Les photos manquantes restent
hors de ces listes effectives. Lieux et légendes et les sélecteurs des modèles
reçoivent le pool album. `AlbumBuildResult.template_photos` le transmet à
l’Aperçu, au PDF, au préchauffage et à la préparation des originaux.

Les mutations et sélections utilisent `Photo.identity`, jamais un chemin ambigu.
Le chemin n’est plus unique en base. Les anciennes API par chemin refusent les
ambiguïtés. En CLI, `scan --source-id ID` distingue deux occurrences du même dossier.

## Migration

Les projets neufs sont créés directement en SQLite 5. Le schéma publié v0.1.0
(version 1, fixture issue du tag) est normalisé directement vers 5 dans une seule
transaction, annulée entièrement en cas d’échec. Les versions de développement
2/3/4 passent par le même mécanisme. La version courante n’est pas reconstruite.
Identités, candidats et corrections sont conservés ; l’utilisation initiale est
BODY. Les anciennes clés de source sont migrées dans la collection puis supprimées.
Un ancien instantané sans configuration reçoit une source générique séparée.
Le JSON de réglages album évolue indépendamment de 2 vers 3.

Les directives du Plan sont décrites dans [la pagination éditoriale](editorial-pagination.md).

Le lieu textuel et la légende ou description du provider sont conservés comme
propositions importées séparées. Ils n’écrasent jamais les champs éditoriaux.
Une légende importée est recherchable et apparaît comme texte indicatif dans
l’éditeur ; elle n’est pas rendue comme légende éditoriale tant que
l’utilisateur ne l’adopte pas.

## Matérialisation et cache

Les miniatures distantes sont récupérées lors de l’import de l’instantané. Les
originaux ne le sont qu’au moment de l’export PDF (ou d’une autre demande
explicite en qualité originale). Le cache propre au projet repose sur
l’identité stable et la révision du provider. Un original remplace à la même
adresse canonique la miniature initiale : composition, packs et renderers
restent donc indépendants du provider.

## Frontière des providers

Les providers implémentent le protocole `PhotoSource` dans
`photoalbum.sources`. Ils listent collections et assets et savent récupérer
une miniature ou un original. Ils ne dépendent ni de la GUI, ni de la
composition, ni des templates, ni du rendering.

L’adaptateur Synology Photos est confiné à `sources/synology.py`. Il n’effectue
que des appels WebAPI en lecture, gère les variantes des espaces personnel et
partagé, et garde cookies et jetons de session navigateur en mémoire. Le projet
ne stocke que l’adresse du NAS, le chemin d’API non secret, le choix TLS, la
collection et l’identifiant stable de source. Les anciens projets contenant un
nom d’utilisateur restent lisibles, mais les nouveaux n’en ont plus besoin.
L’API Photos étant privée et variable selon les versions, toute la logique des
endpoints, cookies, headers et réponses reste dans cet adaptateur et sa petite
couche d’authentification navigateur.

## Authentification Synology interactive

L’authentification Synology s’effectue dans une fenêtre Qt WebEngine intégrée.
Elle utilise un profil hors-enregistrement, un cache mémoire et aucun cookie
persistant. Photo-Album ne reçoit jamais le mot de passe, le code 2FA, le secret
SSO ni l’approbation Secure SignIn. Après l’ouverture de Synology Photos puis
d’Albums, la couche d’authentification observe le contexte de la vraie requête
WebAPI en lecture et copie en mémoire cookies NAS, SID, SynoToken, endpoint,
Origin et Referer. Elle détruit ensuite le profil navigateur. Le provider valide
ce paquet avec `SYNO.Foto.UserInfo.me` avant de lister les albums.

Fermer le provider oublie seulement la session copiée, sans déconnecter
l’utilisateur de DSM. Une reconnexion attache une nouvelle session sans lister
les assets et sans actualiser l’instantané du projet. La resynchronisation reste
une opération explicite distincte.

### Validation manuelle sur le NAS

1. Dans **Ajouter une source → Synology Photos**, saisir l’URL habituelle du
   NAS puis choisir **Se connecter avec Synology**.
2. Effectuer dans la fenêtre intégrée la connexion Synology, 2FA, SSO, passkey
   ou Secure SignIn.
3. Ouvrir Synology Photos puis **Albums** afin que l’application émette une
   requête WebAPI Photos authentifiée.
4. Attendre « Session Synology Photos détectée », puis choisir **Utiliser cette
   session**.
5. Vérifier que l’identité est validée par l’appel en lecture seule
   `SYNO.Foto.UserInfo.me`.
6. Vérifier que les albums apparaissent ; la sélection d’un album peut importer
   ses miniatures, mais ce contrôle ne doit pas télécharger tous les originaux.
7. Annuler ou fermer la session source et vérifier que la fenêtre navigateur a
   disparu. Rouvrir le projet et vérifier qu’une reconnexion ne modifie pas
   l’instantané avant une resynchronisation explicite.

Un projet distant rouvert peut afficher ses miniatures en cache sans connexion.
Actualiser l’instantané ou exporter des originaux absents du cache demande une
reconnexion pour la session courante.
