# Worker Resource Sizing

Uploads stream to disk in 64KB chunks regardless of size — the numbers below are _decode_ cost,
not file size.

| File type       | Peak RAM per file | Why                                                                 |
| --------------- | ----------------- | ------------------------------------------------------------------- |
| Text / other    | ~10 MB            | streamed disk copy only, no decode                                  |
| Image (8–50MP)  | ~130–800 MB       | ~16 bytes/px; bounded by `UPLOAD_MAX_IMAGE_PIXELS`                  |
| Video, any size | ~50–150 MB        | one seeked keyframe decode, capped at 4K — file size doesn't matter |

**Worker RAM** ≈ `concurrency × per-file peak`, capped per child by
`CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB` (default 1GB). Default concurrency is 4 (`-c 4`) → budget
~4GB if large photos/video are common, less for mostly text/small files.

**Not covered by RAM sizing:** disk space. A file's full size needs ~2x itself free on the media
volume during upload → import → cleanup. `TUS_DISK_HEADROOM_MB` rejects a declared upload upfront
if it wouldn't leave that margin, so one large upload can't starve the volume everyone shares.

If a task needs more time (large file, slow storage), raise `CELERY_TASK_SOFT_TIME_LIMIT` /
`CELERY_TASK_TIME_LIMIT` — don't lower the memory ceiling to compensate; they guard different
failure modes (stuck task vs. unhealthy long-lived worker).

See [server-specs.md](server-specs.md) for a recommended baseline deployment.
