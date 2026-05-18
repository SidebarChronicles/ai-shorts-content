# TikTok Analytics Report — 2026-05-18

Window: **2026-04-18 → 2026-05-18** (30 days)

Source: PostFast `/social-posts/analytics` for socialMediaId `9c922596-fb12-4d7c-bd6d-7208e3e6b84c`

## Channel rollup

_No TikTok metrics returned by PostFast for this window yet._

Common reasons:
- Posts are too new (PostFast typically refreshes TT metrics every few hours).
- Workspace plan is Starter (limited analytics) — upgrade for full counts.
- TikTok itself hasn't populated metrics yet (can take ~24h after publish).

## Per-video

| Case | Match | Impressions | Reach | Likes | Comments | Shares | Clicks |
|---|---|---|---|---|---|---|---|
| SY_01_S_lakecabin | _no PostFast match yet_ | – | – | – | – | – | – |
| SY_02_S_lakecabin | high | _no metrics yet_ | – | – | – | – | – |
| SY_03_R_neighborlawn | _no PostFast match yet_ | – | – | – | – | – | – |

## How to read this report

- **Impressions** is TikTok's view count.
- **Reach** is unique viewers; for short-form `reach ≈ impressions` for low-velocity videos.
- **No retention %** — TikTok doesn't expose per-video retention via API. Manual watch-through % still lives in `output/cross_post_status.json` (`tiktok_retention_pct`).
- **Match = medium / no_match:** PostFast couldn't be matched 1:1 by timestamp+caption. If frequent, consider backfilling `platformPostId` into the tracker on upload.
