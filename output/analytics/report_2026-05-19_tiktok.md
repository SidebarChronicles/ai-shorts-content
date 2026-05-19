# TikTok Analytics Report — 2026-05-19

Window: **2026-05-12 → 2026-05-19** (7 days)

Source: PostFast `/social-posts/analytics` for socialMediaId `9c922596-fb12-4d7c-bd6d-7208e3e6b84c`

## Channel rollup

- **Posts with metrics:** 1 / 3
- **Impressions (views):** 0
- **Reach:** 0
- **Likes:** 0
- **Comments:** 0
- **Shares:** 0
- **Clicks:** 0

## Per-video

| Case | Match | Impressions | Reach | Likes | Comments | Shares | Clicks |
|---|---|---|---|---|---|---|---|
| SY_01_S_lakecabin | _no PostFast match yet_ | – | – | – | – | – | – |
| SY_02_S_lakecabin | high | 0 | – | 0 | 0 | 0 | – |
| SY_03_R_neighborlawn | _no PostFast match yet_ | – | – | – | – | – | – |

## How to read this report

- **Impressions** is TikTok's view count.
- **Reach** is unique viewers; for short-form `reach ≈ impressions` for low-velocity videos.
- **No retention %** — TikTok doesn't expose per-video retention via API. Manual watch-through % still lives in `output/cross_post_status.json` (`tiktok_retention_pct`).
- **Match = medium / no_match:** PostFast couldn't be matched 1:1 by timestamp+caption. If frequent, consider backfilling `platformPostId` into the tracker on upload.
