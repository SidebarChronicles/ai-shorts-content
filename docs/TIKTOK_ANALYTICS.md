# TikTok Analytics — programmatic pull

> **Resolved 2026-05-18:** PostFast's `/social-posts/analytics` natively supports TikTok and returns the metrics we want. **Skipping the TikTok Display API path entirely.** No TikTok developer app, no extra OAuth, no extra cost.

## Context

Until now, basic TikTok counts (views/likes/comments/shares) were not tracked anywhere. Watch-through % stays manual via `cross_post_status.py --gate` because no public API surfaces it.

This doc captures the Phase 2 (Day ~8) revisit flagged in [CROSS_POSTING.md:152-167](CROSS_POSTING.md): now that we have multi-day TT data, are basic counts worth automating?

**Answer:** yes, and cheaper than expected — already covered by the PostFast subscription.

---

## Option survey

| Option | Cost | Effort | Metrics | Verdict |
|---|---|---|---|---|
| **A. PostFast `/social-posts/analytics`** | $0 (in plan) | Low — auth + http client exist | impressions, reach, likes, comments, shares, clicks per post | **Chosen** |
| B. TikTok Display API (own dev app) | $0 | Medium — OAuth, dev app review | view_count, like_count, comment_count, share_count, profile info (incl. follower_count) | **Deferred.** Only adds follower_count over A. Revisit if we want independent verification. |
| C. Apify TikTok scraper | ~$12/mo | Low | Adds retention % | **Skipped.** Retention manual is fine for the coarse 30% YT gate. |
| D. TikTok Business / Marketing API | $0 + heavy review | High | Richer audience demographics | Skipped — review cost > value at this stage. |
| E. Browser automation | $0 | Low | Anything in TT Studio | Skipped — HIGH ban risk per [CROSS_POSTING.md:122](CROSS_POSTING.md). |

---

## PostFast `/social-posts/analytics` reference

Verified from [postfa.st/docs](https://postfa.st/docs) on 2026-05-18.

**Endpoint:** `GET https://api.postfa.st/social-posts/analytics`

**Auth:** header `pf-api-key: <POSTFAST_API_KEY>` — same key already in `.env`.

**Query params:**

| Param | Required | Notes |
|---|---|---|
| `startDate` | yes | ISO 8601, e.g. `2026-05-01T00:00:00.000Z` |
| `endDate` | yes | ISO 8601 |
| `socialMediaIds` | no | comma-separated UUIDs; use `POSTFAST_TIKTOK_CHANNEL_ID` to filter to TT only |

**Pagination:** none — endpoint returns all matching posts in the window.

**Response shape (per post):**

```json
{
  "id": "<postfast post UUID>",
  "content": "<caption>",
  "socialMediaId": "<channel UUID>",
  "platformPostId": "<TikTok video ID, populated after publish>",
  "publishedAt": "2026-05-18T17:32:45.000Z",
  "latestMetric": {
    "likes": 1234, "comments": 56, "shares": 78,
    "impressions": 9012, "clicks": 345, "reach": 6789,
    "extras": { ... },
    "fetchedAt": "2026-05-18T20:00:00.000Z"
  }
}
```

`latestMetric` is `null` until PostFast has pulled stats from TikTok (typically a few hours after publish, then refreshed on PostFast's own cadence).

**Tier note:** PostFast's marketing pages mention "Limited Analytics (Starter), full Analytics (Creator+)". If the workspace is on Starter, some fields may come back null; the fetcher tolerates that.

---

## Mapping PostFast posts back to our case_ids

`output/cross_post_status.json` stores per-case TikTok publish *timestamp* but **not** the PostFast post id or TikTok platform_post_id. To attribute analytics back to a case the fetcher matches on:

1. **Primary — timestamp:** PostFast `publishedAt` vs tracker `tiktok` timestamp, ±5 min slack (PostFast publishes within ~30s of our API call).
2. **Tie-break — caption prefix:** if multiple posts share a minute, compare to `<videos_dir>/<case_id>.tt_caption.txt` first 80 chars.
3. **Unmatched posts** are reported in a separate section so we can see them and fix attribution if needed.

We could backfill `platformPostId` into the tracker on upload to make this 1:1, but it's not blocking — Phase 1 cross-post volume is low enough that timestamp + caption is unambiguous.

---

## What we still don't get

- **Retention % / watch-through %** — no API surfaces this for TikTok. Stays manual via `cross_post_status.py --gate <case> open|closed <pct>` until TikTok ships an Insights API or we revisit Apify.
- **Follower count / profile-level metrics** — would need either the PostFast dashboard (manual) or Option B (Display API). Not pursued yet.
- **Per-second retention curve** — same as above; not available without paid scrapers.

---

## When to revisit

- **If PostFast `latestMetric` is consistently null for TikTok** (tier limitation or PostFast not refreshing) → escalate to Option B (Display API, free, ~1-2h work given OAuth template already exists).
- **If retention % becomes the bottleneck for tuning** → revisit Apify Option C ($12/mo).
- **If we need follower_count for goal-tracking** → Option B.
