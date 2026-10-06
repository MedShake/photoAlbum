# Photo sources

Photo-Album treats a source as a read-only collection of assets. A photo is
identified by `source_id + asset_id`; its local `path` is only a materialized
representation used by the existing renderers.

## Snapshot semantics

Selecting or refreshing a collection creates an explicit snapshot in the
project database. Changes in the remote album do not affect an existing
project until the user requests synchronization. During that refresh:

- provider metadata and the provider's original values are updated;
- manual dates, coordinates, captions, and editorial locations are preserved;
- disappeared assets are marked missing instead of being deleted;
- missing status is updated only for the refreshed source; other sources are untouched.

## Multiple source occurrences

The ordered `sources` table and `SourceRepository` are the sole source of
configuration. Each occurrence has a persistent UUID, provider kind, non-secret
configuration, enabled state and its own Date/GPS/Location/Nominatim policy.
Local recursion is part of that source's configuration. The ID never implies
the provider type. Several sources can refer to the same directory or server.

Photos provides three groups: Add a source, Album sources, and Refresh photos.
Disabling a source hides its photos throughout the application without deleting
its snapshot or manual corrections; enabling restores them immediately. Delete
requires confirmation and removes only that occurrence and its database photos.
Independent provider sessions coexist. Analysis/synchronization runs active
sources sequentially and logs individual failures without stopping other sources.
Modifying/reconnecting an unchanged Synology collection does not refresh it.

The source registry remains a small provider factory registry, not a GUI plugin
system. Local-directory and Synology authentication editors remain explicit;
storage, metadata policies, listing and refresh accept arbitrary provider IDs/types.

`Photo.identity` is the mutation/selection key. `photos.path` is indexed but no
longer unique. Legacy path-based APIs reject ambiguous paths instead of editing
an arbitrary photo. CLI scans reuse a uniquely matching configured directory;
use `scan --source-id ID` to distinguish duplicate local occurrences.

## Photo usage and canonical pools

The Actions column offers an explicit radio dialog for `body`, `template_only`
and `off`. This persistent status survives scans and imports and is independent
of missing status and source activation. `ProjectService.list_photos()` includes
all usages from active sources; `list_album_photos()` excludes OFF;
`list_body_photos()` includes only BODY. Missing photos remain outside these
effective lists. Places/captions and template selectors use the album pool.

`AlbumBuildResult.template_photos` carries that canonical pool to preview, PDF,
render prewarming and original preparation. Chronological pagination and body
photo counts use only BODY. See [editorial pagination](editorial-pagination.md).

## Persistence compatibility

SQLite schema 5 is created directly for new projects. The published v0.1.0
schema (version 1) is normalized directly, transactionally, to schema 5; development
versions 2/3/4 use the same normalizer. The published schema fixture is copied
from the `v0.1.0` tag. Any failure rolls back DDL and data together. An already
current database is not rebuilt. Original candidates, manual/editorial data and
stable asset identities are retained, usage defaults to BODY, and source settings
move from legacy metadata keys to `SourceRepository`. Legacy keys are then removed.
Unconfigured historical development snapshots get a separate generic snapshot
source rather than guessing a provider from their ID.

The provider's location label and caption/description are stored separately as
imported suggestions. They never overwrite editorial fields. An imported
caption is searchable and appears as the caption editor's placeholder; it is
not rendered as an editorial caption until the user adopts it.

## Materialization and cache

Remote thumbnails are fetched while the snapshot is imported. Originals are
not fetched until PDF export (or another explicit original-quality request).
The project-scoped cache uses stable asset identities and provider revisions.
An original upgrades the same canonical cache path previously occupied by the
thumbnail, which lets composition code, template packs, and renderers remain
provider-independent.

## Provider boundary

Providers implement the `PhotoSource` protocol in `photoalbum.sources`. They
list collections and assets and can fetch a thumbnail or an original. Provider
code has no GUI, composition, template, or renderer dependency.

The Synology Photos adapter is confined to `sources/synology.py`. It uses only
read-only WebAPI calls, handles Personal/Shared Space API prefixes, and keeps
browser cookies and session tokens in memory. The project stores only the NAS
address, non-secret API path, TLS preference, selected collection, and stable
source id. Older project records that contain a username remain readable, but
new records do not need one. Because the Synology Photos API is private and
version-dependent, all endpoint, cookie, header, and response-shape
compatibility logic stays inside that adapter and its small browser-auth layer.

## Synology interactive authentication

Synology authentication takes place in an embedded Qt WebEngine window. The
window uses an off-the-record profile with an in-memory cache and no persistent
cookies. Photo-Album never receives the password, 2FA code, SSO secret, or
Secure SignIn approval. After the user opens Synology Photos and Albums, the
auth layer observes the actual read-only WebAPI context and copies the NAS
cookies, SID, SynoToken, endpoint, Origin, and Referer into an in-memory session
bundle. It then destroys the browser profile. The provider validates the bundle
with `SYNO.Foto.UserInfo.me` before listing albums.

Closing the provider only forgets the copied session; it does not log the user
out of DSM. Reconnecting attaches a new session without listing assets or
refreshing the project snapshot. Resynchronization remains a separate explicit
operation.

### Manual NAS validation

1. In **Add source → Synology Photos**, enter the normal NAS URL and choose
   **Connect with Synology**.
2. Complete the Synology login, 2FA, SSO, passkey, or Secure SignIn flow in the
   embedded window.
3. Open Synology Photos and select **Albums** so the application emits an
   authenticated Photos WebAPI request.
4. Wait for “Synology Photos session detected”, then choose **Use this
   session**.
5. Confirm that identity validation succeeds through the read-only
   `SYNO.Foto.UserInfo.me` call.
6. Confirm that the album list appears; selecting an album may import its
   thumbnails, but this check must not download every original.
7. Cancel or close the source session and confirm that the browser window is
   gone. Reopen the project and verify that reconnecting does not alter its
   snapshot until an explicit resynchronization.

An opened remote project may display cached thumbnails without reconnecting.
Refreshing the snapshot or exporting uncached originals requires the user to
reconnect for the current application session.
