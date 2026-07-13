# Streaming with OBS

This app accepts live streams over RTMP. Each stream you publish to is authenticated by a **per-stream token** that the app mints for you ahead of time.

## Requirements

- [OBS Studio](https://obsproject.com/) (or any RTMP-compatible encoder)
- The server's RTMP host — your site admin can provide this, or you can read it off the Go Live modal (see below). Default port is **1935**.

## Creating a stream and getting its server URL

Stream tokens are scoped to a single stream and must exist before you publish — RTMP `on_publish` is rejected if the supplied `stream_token` doesn't match an existing stream row.

In the web UI:

1. Click **Go Live** in the navbar.
2. Enter a **Stream Name** — letters, numbers, hyphens, and underscores, up to 64 characters. This becomes the URL slug at `/live/<name>/`.
3. Click **Create / Get Token**. The modal then shows:
   - The **Stream Token** (per-stream — leaking it never exposes your account)
   - A ready-to-paste **RTMP Server URL** of the form `rtmp://<host>/live?stream_token=<token>`
4. Optionally set a **Title** — it will be appended to the server URL as `&title=…`.

Use the **Rotate** button to invalidate the current token and mint a new one if it ever leaks.

## OBS Setup

1. Open OBS and go to **Settings → Stream**.
2. Set **Service** to `Custom...`.
3. Set **Server** to the RTMP Server URL from the Go Live modal:

   ```text
   rtmp://your-domain.com/live?stream_token=YOUR_STREAM_TOKEN
   ```

4. Set **Stream Key** to your stream name (e.g. `my-stream`).
5. Click **OK**, then **Start Streaming**.

The stream page will be available at `https://your-domain.com/live/<name>/` while you're connected.

## Optional Parameters

Optional metadata is appended as query params on the **Server URL**. OBS sends the full server URL to the server on `on_publish`, so anything passed here is applied at stream start (and re-applied on every reconnect, overwriting any edits made via the web UI).

| Parameter      | Type    | Description                                          |
| -------------- | ------- | ---------------------------------------------------- |
| `title`        | string  | Stream title shown on the stream page                |
| `description`  | string  | Short description shown below the title              |
| `public`       | boolean | `true` makes the stream visible to anyone            |
| `viewer_limit` | integer | Maximum number of concurrent viewers (0 = unlimited) |
| `record`       | boolean | `true` saves this session's recording (see below)    |

Example:

```text
rtmp://your-domain.com/live?stream_token=YOUR_STREAM_TOKEN&title=My+Stream&description=Tune+in&public=true&viewer_limit=100&record=true
```

> Setting a **password** is not supported via the RTMP query string — set it from the stream page after publishing (see below).

## Recording & Past Streams

Every stream session (from publish to disconnect) is logged as a **past stream** with its title/description snapshot, start/end time, and peak/average viewer count — visible from the **Streams** table context menu under **Recordings**, regardless of whether recording was enabled.

To also save the video:

- Check **Record this stream** in the Go Live modal, or
- Toggle **Enable Recording** / **Disable Recording** from a stream's context menu, or
- Add `&record=true` to the RTMP server URL (see Optional Parameters above)

When recording is on, the finished video is imported as a regular file the moment the stream ends — it shows up in your file gallery like any other upload and is linked from that session's row in the Recordings modal.

Two retention limits are available per stream (both optional, set from the Recordings modal):

| Setting                     | Behavior                                                        |
| ---------------------------- | ---------------------------------------------------------------- |
| Expire after (days)         | Recording is deleted this many days after the stream started    |
| Keep at most (count)        | Only the N most recent recordings are kept; older ones are deleted |

Leaving both blank keeps recordings indefinitely. Deleting a recording never deletes the past-stream entry itself — only the video file.

## Resuming a Stream

You can reuse a stream name (and its `stream_token`) to resume a previous stream. The `started_at` timestamp resets each time you reconnect.

If you have `title` / `description` baked into the OBS server URL, those values overwrite any web-UI edits each time you reconnect — leave them out of the URL if you want to edit metadata from the stream page.

## Network Setup

RTMP uses **port 1935**. It must be reachable from the machine running OBS.

**Docker** — port 1935 is not exposed by default. Add it to the nginx service in your `docker-compose.yaml`:

```yaml
ports:
  - '80:80'
  - '1935:1935'
```

**Home network** — if the server is behind a home router, forward TCP port 1935 to the server's local IP. OBS should use your public IP or DDNS hostname externally, or the server's private IP on the LAN.

### Recording storage (self-hosted / custom compose)

Recordings are written by the `nginx` container to `/data/media/record` and then read, remuxed, and deleted by the `app`/`worker` containers — so that path must live on the same shared `media_dir` volume already mounted at `/data/media` in all three services (this is the default in the provided `docker-compose*.yaml` files; no action needed there). If you're running a custom compose setup, make sure that volume is mounted in `nginx`, `app`, and `worker`, and don't restrict `/data/media/record` to a single container's user — nginx and the app/worker both need to create and delete files there.

## Private Streams and Passwords

Two independent gates control who can watch a stream. They compose:

| Setting        | Who can watch                                             |
| -------------- | --------------------------------------------------------- |
| `public=true`  | Anyone with the link                                      |
| `public=false` | Only signed-in users                                      |
| `password` set | Viewer must enter the password (in addition to the above) |

Access to `/hls/...` is decided by nginx via an `auth_request` subrequest into Django. The request is allowed if **any** of the following holds:

1. The viewer's `hls_sig` / `hls_exp` cookies validate — these are issued when the viewer loads `/live/<name>/` and prove they passed the auth + password gate. The cookies auto-refresh in the background so long viewing sessions don't drop.
2. The request carries `?token=<playback_token>` matching the stream's owner-issued raw-link token (see "Watching from a native client" below).
3. The stream is **public and not password-protected** — anonymous direct requests to `/hls/...` keep working with no token or cookie.

Private streams and password-protected streams require option 1 or 2.

### Setting or changing the password

Set the password from the **stream page** (owners see an extra controls panel) or from the **Streams** table context menu. Share the password out-of-band with viewers — they'll be prompted for it on first load.

### Watching from a native client

There are two options depending on what the player can do:

**1. Cookie-based** (for clients that can carry cookies across requests, e.g. the Django Files mobile app):

```text
GET /api/stream/hls-token/<stream-name>/?password=<password>
Authorization: Bearer <YOUR_API_TOKEN>
```

- `Authorization` is only required for private streams; public streams accept anonymous calls.
- `?password=…` is only required when the stream has a password set.
- The response sets `hls_sig` / `hls_exp` cookies that the player must include on subsequent `/hls/...` fetches. The same endpoint refreshes them — call it again at roughly half the cookie TTL.

**2. Raw link** (for players that can't carry cookies — VLC, ffmpeg, generic HLS players):

On the **Streams** table, open the row's context menu and click **Enable Raw Link** — this mints a `playback_token` for that stream. Click **Copy Raw Link** to copy a URL of the form:

```text
https://your-domain.com/hls/<stream-name>.m3u8?token=<playback_token>
```

Paste that into any HLS player. **Disable Raw Link** clears the token and immediately invalidates every previously-issued raw link (after the nginx auth cache TTL elapses for already-validated tokens). Re-enabling rotates the token.

The `playback_token` is independent of the RTMP `stream_token`, so leaking a raw link never grants ingest access.

## API Tokens

Bearer authentication for the JSON API (uploads, stream management, mobile clients) uses **API Tokens** managed under **Settings → Account → API Tokens**. Each token has a name, optional expiry, and can be disabled or deleted individually. Tokens are stored hashed at rest — the plaintext is shown only once at creation.

Treat each token like a password. API tokens are **not** accepted for RTMP publishing — that flow uses the per-stream `stream_token` described above.
