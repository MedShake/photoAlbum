# Releasing Photo Album

**English** | [Français](RELEASING.fr.md)

This document describes how to publish a new Photo Album release.

## 1. Update the version

Update the project version in `pyproject.toml`, for example:

    version = "1.2.0rc1"

`pyproject.toml` is the single source of truth for the application
version. Do not update a version string anywhere else.

## 2. Refresh the editable installation

When developing from an editable installation, refresh the installed
package metadata after changing the version:

    python -m pip install -e .

This ensures that the application, `importlib.metadata`, the About
dialog, and the HTTP User-Agent all see the new version.

## 3. Run the test suite

Before preparing the release:

    pytest

All tests must pass.

## 4. Commit and push

Commit the version change and any other changes intended for the release:

    git add pyproject.toml
    git commit -m "Prepare 1.2.0rc1 release"
    git push origin main

Check that the GitHub CI workflow completes successfully.

## 5. Create the GitHub Release

On GitHub:

1. Open **Releases**.
2. Select **Draft a new release**.
3. Create a tag named `v<version>`, for example `v1.2.0rc1`.
4. Make sure the tag targets the intended commit on `main`.
5. Add the release title and release notes.
6. Publish the release.

The GitHub Release tag must exactly match the version from
`pyproject.toml`, prefixed with `v`.

For example:

    pyproject.toml : 1.2.0rc1
    GitHub tag     : v1.2.0rc1
    Debian version : 1.2.0~rc1

The release workflow checks this correspondence automatically.

## 6. Automated builds

Publishing the GitHub Release triggers the release workflow.

GitHub Actions automatically builds and verifies:

- the Linux PyInstaller application bundle;
- the Debian package;
- the Windows PyInstaller application bundle;
- the Windows installer.

The Debian package and Windows installer are then attached directly to
the GitHub Release. The workflow also publishes stable-name aliases used by
the permanent download links in the README.

For version `1.2.0rc1`, the release assets will look like:

    photo-album_1.2.0~rc1_amd64.deb
    PhotoAlbum-1.2.0rc1-Windows-x64-Setup.exe
    photo-album_latest_amd64.deb
    PhotoAlbum-latest-Windows-x64-Setup.exe

## 7. Verify the published release

After the workflow completes:

1. Check that all release jobs are green.
2. Open the GitHub Release.
3. Check that the versioned `.deb` and Windows `Setup.exe`, together with their `latest` aliases, are present in **Assets**.
4. For important releases, install and launch the published packages on
   Linux and Windows as a final smoke test.

## Manual release builds

The **Release builds** workflow can also be started manually from the
GitHub Actions interface.

A manual run builds the packages as workflow artifacts but does not
attach them to a GitHub Release.
