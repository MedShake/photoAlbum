# Photo sources

Photo-Album treats a source as a read-only collection of assets. A photo is
identified by `source_id + asset_id`; its local `path` is only a materialized
representation used by the existing renderers.

## Snapshot semantics

Selecting or refreshing a collection creates an explicit snapshot in the
project database. Changes in the remote album do not affect an existing
project until the user requests another analysis. During that refresh:

- provider metadata and the provider's original values are updated;
- manual dates, coordinates, captions, and editorial locations are preserved;
- disappeared assets are marked missing instead of being deleted;
- assets from a previously selected source are retained but made inactive.

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
