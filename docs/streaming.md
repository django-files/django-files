# Streaming with OBS

This app accepts live streams over RTMP. Streams are created automatically the first time you connect with a given stream key.

## Requirements

- [OBS Studio](https://obsproject.com/) (or any RTMP-compatible encoder)
- Your **auth token** — find it on your account settings page under "Authorization Token"
- The server's **RTMP URL** — your site admin can provide this (format: `rtmp://your-domain.com/live`)

## OBS Setup

1. Open OBS and go to **Settings → Stream**
2. Set **Service** to `Custom...`
3. Set **Server** to:

   ```text
   rtmp://your-domain.com/live?token=YOUR_AUTH_TOKEN
   ```

4. Set **Stream Key** to:

   ```text
   your-stream-name
   ```

   Replace `your-stream-name` with any short identifier (letters, numbers, hyphens). This becomes the stream's URL slug.

5. Click **OK**, then click **Start Streaming** in OBS.

The stream page will be available at `https://your-domain.com/live/your-stream-name/` once you connect.

## Setting a Title and Description

Optional metadata is passed as query parameters on the **Server URL**. OBS sends the full server URL to the server on connect, so params there are available at stream start:

```text
rtmp://your-domain.com/live?token=YOUR_AUTH_TOKEN&title=My+Stream+Title&description=Stream+description+here
```

You can also edit the title and description live from the stream page after connecting.

## Optional Parameters

All optional parameters are appended to the Server URL (after the token):

| Parameter      | Type    | Description                                  |
| -------------- | ------- | -------------------------------------------- |
| `title`        | string  | Stream title shown on the stream page        |
| `description`  | string  | Short description shown below the title      |
| `public`       | boolean | `true` makes the stream publicly visible     |
| `viewer_limit` | integer | Maximum number of concurrent viewers allowed |

Example with all options:

```text
rtmp://your-domain.com/live?token=YOUR_AUTH_TOKEN&title=My+Stream&description=Tune+in&public=true&viewer_limit=100
```

## Resuming a Stream

You can reuse any stream key to resume a previous stream. The stream record is updated with `is_live=true` and the start time is reset. Past stream history (viewer counts, recordings) is preserved.

Note that having the title and description set in your URL will OVERWRITE any change made to the title and description in Django Files when a stream starts or restarts.

## Finding Your Auth Token

Go to **Settings → Account** in the web UI. Your authorization token is listed there. Keep it secret — anyone with your token can stream to your account.

The stream page for any stream you own also has a **Copy OBS Server URL** button that copies the server URL (with your token) for easy pasting into OBS.
