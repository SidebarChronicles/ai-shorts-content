# Cross-posting to Instagram Reels + TikTok (manual workflow)

> **Why manual:** Full API automation costs 4-6 weeks of Meta + TikTok app review. Buffer/Metricool ($12/mo) works in a day but adds a vendor dependency. We picked manual cross-post first; revisit after Phase 1 data (Day 7) tells us if cross-platform views move the needle.

**Target time per video:** ≤3 minutes (AirDrop + paste caption + tap post × 2 platforms).

---

## The workflow (per video)

### Step 1 — See what's pending

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
python3 scripts/cross_post_status.py --pending
```

Shows every YouTube-posted video that hasn't been cross-posted to IG or TikTok yet.

### Step 2 — Pull the bundle for one video

```bash
python3 scripts/cross_post_status.py --airdrop SY_01_S_lakecabin
```

Prints:
- The MP4 file path on disk
- The IG caption (formatted for emoji + line breaks)
- The TikTok caption (formatted as a punchy 1-liner)
- The two commands to mark done after posting

### Step 3 — Get the MP4 onto your phone

Three options, fastest first:

1. **AirDrop** (recommended) — In Finder, navigate to `output/story_videos/`, right-click the `.mp4` → Share → AirDrop → your phone. ~5 seconds.
2. **iCloud Drive** — Move the file to `~/Documents` (synced to iCloud). Open Files app on phone, save to camera roll.
3. **iMessage to yourself** — Drag the MP4 into the Messages app on Mac, send to "You". Receive on phone, save to camera roll.

Whichever method: the goal is having the MP4 in your phone's camera roll.

### Step 4 — Post to Instagram Reels

1. Open Instagram app → tap `+` (new post) → **Reel** tab
2. Select the video from your camera roll
3. **Skip** any IG editing — the video is already finished. Just tap "Next."
4. Cover: leave default (first frame is what we designed for)
5. **Paste the IG caption** from the airdrop bundle output (you can `pbcopy < ig_caption.txt` from terminal to copy it, then paste in IG)
6. **⚠️ Required: tap "Advanced settings" → toggle "AI-generated content" ON.** Meta requires this for AI-narrated videos since 2024. Skipping it can mute distribution permanently.
7. Tap "Share" → "Share to Reels."

### Step 5 — Post to TikTok

1. Open TikTok app → tap `+`
2. **"Upload"** → select the same video from camera roll
3. Skip the TikTok editing — tap "Next."
4. **Paste the TikTok caption** (different from IG — punchier, fewer hashtags)
5. **⚠️ Required: tap "More options" → toggle "AI-generated content" ON.** TikTok requires this for AI shorts since 2024. Same penalty as IG if skipped.
6. Cover: use the first frame (the suggested default works fine for our format).
7. Tap "Post."

### Step 6 — Mark done in the tracker

```bash
python3 scripts/cross_post_status.py --mark SY_01_S_lakecabin ig
python3 scripts/cross_post_status.py --mark SY_01_S_lakecabin tt
```

That removes this video from `--pending` and timestamps when it landed on each platform.

---

## Quick reference

**One-line copy IG caption to clipboard:**
```bash
pbcopy < output/story_videos/SY_01_S_lakecabin.ig_caption.txt
```

**One-line copy TikTok caption:**
```bash
pbcopy < output/story_videos/SY_01_S_lakecabin.tt_caption.txt
```

**Regenerate captions (e.g. after updating description.md):**
```bash
python3 scripts/build_captions.py --case SY_01_S_lakecabin --videos-dir output/story_videos --force
```

**Generate captions for every YouTube-posted video that doesn't have them yet:**
```bash
python3 scripts/build_captions.py --all-pending --videos-dir output/story_videos
```

---

## Gotchas + best practices

### Don't add a watermark

We don't apply any platform brand watermark to our MP4s, and **we shouldn't**:
- Instagram demotes videos with visible TikTok/CapCut/YouTube watermarks by 30-50% (Originality Score + visual fingerprinting, 2026 algorithm)
- TikTok suppresses content with competitor watermarks but is less aggressive
- A single unbranded MP4 works clean on all 3 platforms — keep it that way

### AI disclosure is non-negotiable

Both IG and TikTok require the AI-content toggle on AI-narrated videos:
- IG: "Advanced settings" → "AI-generated content"
- TikTok: "More options" → "AI-generated content"
- Skipping it can result in permanent shadow-banning. Our captions include "⚠️ AI-narrated story" inline as a belt-and-suspenders disclosure.

### Caption length tuning

| Platform | Sweet spot | Why |
|---|---|---|
| IG Reels | 100-300 chars | IG cuts at ~125 chars in feed; you want the hook in the visible portion |
| TikTok | 80-150 chars | TT shows the whole caption; longer = more skimmable but less punchy |

Our generator targets these ranges. If a caption is way off, regenerate with `--force` or hand-edit the file before pasting.

### Hashtag count

Both platforms now favor **fewer, more-specific hashtags** (algorithm changed in 2024-2025):
- IG: 3-5 hashtags mixed with text > 30 hashtag wall
- TikTok: 3-5 hashtags at end > hashtag soup

Our captions pick 5 from the YouTube tag pool. Don't add more by hand.

### Music: leave the CC-BY track in

Instagram and TikTok both have native music libraries. You might be tempted to swap our Kevin MacLeod CC-BY track for a TikTok-trending sound for algorithmic boost. **Don't:**
- Our music attribution is required by the CC-BY 4.0 license
- Mixing TT-native music with the same MP4 across platforms breaks the consistency
- IG/TikTok both fingerprint visual content, not audio — the CC-BY track is fine

If a specific TikTok sound trends hard, regenerate ONE video with that sound (manual TikTok editor flow) rather than swapping everything.

---

## Backlog (revisit at Day 7)

Once we have 7 days of cross-post data:

| Trigger | Action |
|---|---|
| Cross-platform drives ≥30% of total views | Automate via Meta + TikTok APIs (4-6 weeks dev) OR switch to Buffer ($12/mo) |
| Cross-platform drives <10% of total views | Drop manual work, focus on YouTube |
| 24 min/day of tapping becomes painful before Day 7 | Switch to Buffer ($12/mo) — same outcome, less friction |

The Day 7 phase-transition decision in `docs/RELEASE_SCHEDULE.md` includes a "kept_verticals" reduction — cross-posting effort should be limited to whichever verticals survive that cut.
