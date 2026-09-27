# Publier une version de Photo Album

[English](RELEASING.md) | **Français**

Ce document décrit la procédure de publication d’une nouvelle version de Photo Album.

## 1. Mettre à jour la version

Modifiez la version du projet dans `pyproject.toml`, par exemple :

    version = "1.2.0rc1"

`pyproject.toml` est l’unique source de vérité pour la version de l’application. Ne modifiez aucune autre chaîne de version ailleurs.

## 2. Actualiser l’installation éditable

Lors du développement avec une installation éditable, actualisez les métadonnées du paquet après avoir changé la version :

    python -m pip install -e .

Ainsi, l’application, `importlib.metadata`, la boîte de dialogue À propos et le User-Agent HTTP voient tous la nouvelle version.

## 3. Exécuter les tests

Avant de préparer la publication :

    pytest

Tous les tests doivent réussir.

## 4. Commiter et pousser

Commitez le changement de version et les autres modifications prévues pour cette publication :

    git add pyproject.toml
    git commit -m "Prepare 1.2.0rc1 release"
    git push origin main

Vérifiez ensuite que le workflow CI GitHub se termine avec succès.

## 5. Créer la GitHub Release

Sur GitHub :

1. ouvrez **Releases** ;
2. choisissez **Draft a new release** ;
3. créez un tag `v<version>`, par exemple `v1.2.0rc1` ;
4. vérifiez que le tag cible le commit voulu sur `main` ;
5. ajoutez le titre et les notes de version ;
6. publiez la release.

Le tag de la GitHub Release doit correspondre exactement à la version de `pyproject.toml`, précédée de `v`.

Par exemple :

    pyproject.toml : 1.2.0rc1
    GitHub tag     : v1.2.0rc1
    Debian version : 1.2.0~rc1

Le workflow de publication vérifie automatiquement cette correspondance.

## 6. Builds automatisés

La publication de la GitHub Release déclenche le workflow de release.

GitHub Actions construit et vérifie automatiquement :

- le bundle Linux PyInstaller ;
- le paquet Debian ;
- le bundle Windows PyInstaller ;
- l’installeur Windows.

Le paquet Debian et l’installeur Windows sont ensuite attachés directement à la GitHub Release. Le workflow publie également des alias à nom stable utilisés par les liens de téléchargement permanents du README.

Pour la version `1.2.0rc1`, les fichiers publiés ressemblent à :

    photo-album_1.2.0~rc1_amd64.deb
    PhotoAlbum-1.2.0rc1-Windows-x64-Setup.exe
    photo-album_latest_amd64.deb
    PhotoAlbum-latest-Windows-x64-Setup.exe

## 7. Vérifier la version publiée

Une fois le workflow terminé :

1. vérifiez que toutes les tâches de publication sont au vert ;
2. ouvrez la GitHub Release ;
3. vérifiez que le `.deb` et le `Setup.exe` Windows versionnés, ainsi que leurs alias `latest`, sont présents dans **Assets** ;
4. pour les versions importantes, installez et lancez les paquets publiés sous Linux et Windows comme test final rapide.

## Builds manuels de release

Le workflow **Release builds** peut aussi être lancé manuellement depuis l’interface GitHub Actions.

Un lancement manuel construit les paquets comme artefacts du workflow, mais ne les attache pas à une GitHub Release.
