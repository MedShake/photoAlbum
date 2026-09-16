# Releasing Photo Album

This document describes how to publish a new Photo Album release.

## 1. Update the version

Update the project version in `pyproject.toml`, for example:

    version = "0.1.0b2"

The version in `pyproject.toml` is the reference version used by the
packaging tools.

## 2. Run the test suite

Before preparing the release:

    pytest

All tests must pass.

## 3. Commit and push

Commit the version change and any other changes intended for the release:

    git add pyproject.toml
    git commit -m "Prepare 0.1.0b2 release"
    git push origin main

Check that the GitHub CI workflow completes successfully.

## 4. Create the GitHub Release

On GitHub:

1. Open **Releases**.
2. Select **Draft a new release**.
3. Create a tag named `v<version>`, for example `v0.1.0b2`.
4. Make sure the tag targets the intended commit on `main`.
5. Add the release title and release notes.
6. Publish the release.

The GitHub Release tag must exactly match the version from
`pyproject.toml`, prefixed with `v`.

For example:

    pyproject.toml : 0.1.0b2
    GitHub tag     : v0.1.0b2
    Debian version : 0.1.0~b2

The release workflow checks this correspondence automatically.

## 5. Automated builds

Publishing the GitHub Release triggers the release workflow.

GitHub Actions automatically builds and verifies:

- the Linux PyInstaller application bundle;
- the Debian package;
- the Windows PyInstaller application bundle;
- the Windows installer.

The Debian package and Windows installer are then attached directly to
the GitHub Release.

For version `0.1.0b2`, the release assets will look like:

    photo-album_0.1.0~b2_amd64.deb
    PhotoAlbum-0.1.0b2-Windows-x64-Setup.exe

## 6. Verify the published release

After the workflow completes:

1. Check that all release jobs are green.
2. Open the GitHub Release.
3. Check that the `.deb` and Windows `Setup.exe` are present in **Assets**.
4. For important releases, install and launch the published packages on
   Linux and Windows as a final smoke test.

## Manual release builds

The **Release builds** workflow can also be started manually from the
GitHub Actions interface.

A manual run builds the packages as workflow artifacts but does not
attach them to a GitHub Release.
