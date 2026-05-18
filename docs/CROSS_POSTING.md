# Cross-posting to Instagram Reels + TikTok (autonomous via PostFast)

> **v2 update (May 18 2026):** Manual AirDrop workflow retired. PostFast (~$15/mo) fronts TikTok Content Posting API + Meta Graph API via their pre-approved developer apps, so we don't have to file our own app reviews (2-6 week wait). Cross-post is now driven by the routine's STEP 4; no daily human action needed for upload itself.

**Daily human time:** ~3 min/morning (eyeball TT Studio for 48h-old cases → `--gate` flip). Down from ~24 min/day of manual AirDropping.

---

## How it works

1. Each fire renders ≤2 videos, uploads gate-open ones to YouTube, generates IG + TT caption sidecars (`build_captions.py`).
2. SKILL.md STEP 4 then calls `scripts/post_via_scheduler.py --all-pending`, which:
   - Loads `output/cross_post_status.json` to find cases with `tiktok==null` or `instagram==null`.
   - POSTs each MP4 + matching caption sidecar to PostFast's `/v1/posts` endpoint with `ai_generated=true` (forwarded as the platform-mandated AI-content flag).
   - On 2xx: marks the timestamp in tracker (atomic write).
   - On any failure: leaves tracker untouched. Next fire retries the same (case, platform) pair while skipping ones that already posted. **Idempotent.**
3. 48h later you eyeball TT Studio for retention %, then `--gate open|closed <pct>`. Next fire's STEP 4 YouTube upload pass picks up gate-open cases.

---

## One-time setup

### 1. PostFast account

1. Sign up at https://postfa.st. Pick the cheapest plan that includes:
   - TikTok channel
   - Instagram Reels channel
   - REST API access
2. Connect your TikTok account via PostFast dashboard (OAuth flow).
3. Connect your Instagram account. **Required:** IG must be a **Business** account linked to a Facebook Page. If yours is Personal/Creator, switch in the IG app → Settings → Account type → Switch to Business.
4. Generate an API key in the PostFast dashboard.
5. Copy the TikTok + Instagram channel UUIDs from the dashboard's Channels page.

### 2. Project env

Add to `.env`:

```
POSTFAST_API_KEY=<bearer token from PostFast>
POSTFAST_TIKTOK_CHANNEL_ID=<TikTok channel UUID>
POSTFAST_INSTAGRAM_CHANNEL_ID=<Instagram channel UUID>
```

(`.env.example` carries the same placeholders, gitignored real values.)

### 3. Smoke-test

```bash
# Verify the API key + channel IDs are wired up
python3 scripts/post_via_scheduler.py --check-auth

# Dry-run against the current tracker (no uploads, just lists what would post)
python3 scripts/post_via_scheduler.py --all-pending --dry-run
```

### 4. First real post

Push a single case manually before letting the routine auto-queue:

```bash
python3 scripts/post_via_scheduler.py --case SY_05_H_basement
```

Confirm:
- Both platforms show the video as published / scheduled within 5 min (check PostFast dashboard's Posts tab).
- `output/cross_post_status.json` shows ISO timestamps in `tiktok` and `instagram` fields for that case.

After that, the routine takes over.

---

## Daily ritual (~3 min)

```bash
# 1. See yesterday's fires fired (sanity)
ls -lt output/scripts/ | head -8

# 2. Check the gate status — what's awaiting YouTube upload?
python3 scripts/cross_post_status.py --gate-status

# 3. For any case ≥48h old still in "pending", eyeball TT Studio for watch-through %:
#    Open TikTok Studio app → Content → tap video → Analytics → Watch time + Watched full video %
#    Then flip the gate:
python3 scripts/cross_post_status.py --gate SY_05_H_basement open 34.2     # ≥30% → safe for YT
python3 scripts/cross_post_status.py --gate SY_04_H_attic closed 18.7      # <30% → stays on TT+IG only

# 4. Budget check
python3 scripts/revenue_tracker.py --break-even-check
```

That's it. PostFast handles upload; you only weigh in on the gate.

---

## Failure modes + how to handle them

| Symptom | Cause | Fix |
|---|---|---|
| `POSTFAST_API_KEY missing` | `.env` not loaded or key blank | Confirm `.env` has the key; rerun `--check-auth` |
| `HTTP 401` from PostFast | Key revoked or expired | Regenerate key in PostFast dashboard; update `.env` |
| `HTTP 403` from PostFast | Channel UUID mismatch | Re-copy from dashboard; check you're using TT id for `--platforms tt`, not IG |
| `HTTP 422` mentioning AI flag | TikTok rejected the AI-content flag | PostFast surfaces; rerun after PostFast retries (usually transient) |
| `missing bundle files` | Caption sidecars not generated | Run `python3 scripts/build_captions.py --case <id> --videos-dir <dir> --force` |
| One platform succeeds, other fails | Per-platform handling — tracker marks only successful one | Re-run script; only the failed platform retries |
| PostFast TT auth revoked (platform side) | TikTok session expired in PostFast | Re-OAuth via PostFast dashboard, ~5 min |

If PostFast is fully down (rare), revert temporarily to the manual workflow:
1. `python3 scripts/cross_post_status.py --airdrop <case_id>` — prints the MP4 + caption paths.
2. AirDrop the MP4 to your phone, paste captions, post manually.
3. `python3 scripts/cross_post_status.py --mark <case_id> ig` and `--mark <case_id> tt` to update the tracker.

The manual code paths are still in `cross_post_status.py` — they're never removed.

---

## Why PostFast (and not DIY API)

| Approach | Time to autonomous | Monthly cost | Risk |
|---|---|---|---|
| DIY Meta + TikTok app reviews | 3-6 weeks | $0 (after review) | App rejection; one platform approving while the other lags |
| **PostFast scheduler** ✓ | ~3 days | ~$15 | Vendor lock-in; mitigated by month-to-month plan |
| Browser automation | 1-2 days | $0 | **HIGH ban risk** — TikTok 2026 detects Playwright/Selenium fingerprints. One ban = channel dead. |

We picked **PostFast** because Phase 1 (Days 1-7) needs maximum signal velocity. Losing 50% of Phase 1 waiting for app reviews is worse than $15/mo. If the channel doesn't break even by Day 60-90, the scheduler bill stops alongside production.

---

## Compliance — still applies

### AI disclosure
PostFast forwards `ai_generated=true` to both TikTok + IG, satisfying the 2024+ platform requirements for AI-narrated content. Don't disable this flag.

### Music attribution (Kevin MacLeod CC-BY 4.0)
Captions include `🎵 Kevin MacLeod (CC-BY 4.0)` inline. Required by the license. Don't strip it.

### No watermarks
Instagram demotes videos with visible TikTok/CapCut/YouTube watermarks by 30-50%. Our renderer produces clean MP4s — keep it that way.

### Caption length tuning
| Platform | Sweet spot | Why |
|---|---|---|
| IG Reels | 100-300 chars | IG cuts at ~125 chars in feed; hook in visible portion |
| TikTok | 80-200 chars | TT shows the whole caption; punchier = better |

`build_captions.py` already enforces these ranges. If a caption is way off, regenerate with `--force`.

### Hashtag count
Both platforms favor 3-5 specific tags over hashtag walls (2024-2025 algorithm change). Generator picks 5. Don't add more by hand.

---

## Analytics — still manual (intentional)

We deliberately don't pay $12/mo for an Apify TikTok scraper to autonomously fetch follower count / watch %. Reasons:

- The YouTube gate threshold (30% TT watch-through) is coarse — eyeball precision is fine.
- TikTok has no public Insights API for per-video retention; only paid scrapers reach it.
- At 8/day, eyeball check is ~2 min/morning. Revisit at Phase 2 (Day 8) if narrowed verticals warrant higher precision.

For Instagram analytics, PostFast's dashboard surfaces reach + plays + watch time per post. Check there or in the IG app's Insights tab. IG is brand layer; it doesn't gate anything, so the signal is informational only.

---

## When to revisit this setup

- **Day 7 (Phase 1 → 2):** if cross-platform views ≥30% of total, this layer is paying for itself. Continue. If <10%, consider dropping PostFast and focusing on whatever vertical the data favors.
- **Phase 4 (Day 29+):** if TikTok Creator Rewards unlocks (10K + 100K/30d), the $15/mo is dwarfed by revenue. Continue.
- **PostFast pricing change or shutdown:** month-to-month means low switching cost. Re-evaluate Buffer ($18-36/mo) or DIY app review (free, 3-6 weeks).
