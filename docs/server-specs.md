# Recommended Server Specs

| Use case                                            | vCPU | RAM   | Disk        |
| --------------------------------------------------- | ---- | ----- | ----------- |
| Small / personal (mostly text, photos)              | 2    | 4GB   | 20GB+ free  |
| Average (photos + occasional video)                 | 4    | 8GB   | 50GB+ free  |
| Heavy (frequent large video, many concurrent users) | 8    | 16GB+ | 200GB+ free |

Disk must be sized for your largest expected files × concurrent uploads, plus
`TUS_DISK_HEADROOM_MB` margin (default 1GB) — not just total library size.

RAM math and per-service breakdown: [resource-sizing.md](resource-sizing.md).
