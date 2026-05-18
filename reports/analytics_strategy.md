# Analytics Strategy — TrueCrime Shorts Channel

A plan for closing the feedback loop from video performance back to content and pipeline decisions. Written ahead of having data so we can act on signal the moment it arrives.

---

## What YouTube gives us for free

Two APIs, both free at our scale:

| API | What it returns | Quota |
|---|---|---|
| **YouTube Data API v3** | Video metadata, comments, likes/dislikes ratio, subscriber count, list of uploaded videos | 10K units/day (we already use this for uploads at 1,600 units/video) |
| **YouTube Analytics API** | Views, watch time, CTR, retention curve (avg viewer % retained at each second), traffic source, demographics, subscriber gained/lost per video | Separate quota, generous |

Also surfaced in **YouTube Studio** (no API needed, just manual review):
- Frame-level retention graph (shows exactly where viewers drop off)
- "Performance compared to similar videos" benchmark
- Audience retention percentile
- Top search queries leading viewers to the video

For autonomous decision-making we use the Analytics API. For weekly human review, Studio is more visual.

---

## The metrics that matter (in priority order)

### Tier 1 — Drives every decision

**1. Three-second hold (a.k.a. "hook retention")**
Percentage of viewers still watching at 3 seconds. The single most important Shorts metric. Above 70% = the hook is working. Below 50% = rewrite the hook.

What it tells us: **is the title + first sentence pulling the viewer in?**

**2. Average view duration (as % of length)**
Percentage of total length the average viewer watches. Above 80% = pacing is right. Below 60% = something later in the video is losing them.

What it tells us: **does the body of the script earn the hook's promise?**

**3. Click-through rate (CTR) on impressions**
For Shorts, this is "swipe-stop rate" rather than thumbnail CTR. Measured as views ÷ impressions. Above 8% = title is competitive. Below 4% = title is invisible.

What it tells us: **is the title competing well in the feed?**

### Tier 2 — Confirms the lessons from Tier 1

**4. Likes ÷ views ratio**
Above 4% = strong viewer affinity. Below 1% = neutral reception. Negative likes ratio (dislikes > likes) almost never appears in this niche — if it does, the case selection was wrong (offensive framing, victim disrespect).

**5. Comments per 1K views**
Above 5 = engaged audience. Comments are also free editorial input: viewers tell you which cases they want next, which framings landed, which felt off.

**6. Subscriber conversion per video**
New subscribers attributed to a specific video. The most expensive metric to earn — usually 1 sub per 1K–5K views. Cases that over-index here teach us what creates lasting fans vs. just impressions.

**7. Saves and shares**
Saves indicate "I want to come back to this." Shares indicate "I think someone else should see this." Both correlate with monetization eligibility and YPP acceptance.

### Tier 3 — Diagnostic only, don't optimize for

- Demographics (age/gender/country) — informs ad targeting but doesn't change the content
- Traffic source breakdown — useful to know if we're winning home feed vs. search vs. external referrals
- Watch time (raw hours) — important for YPP eligibility (4K hours/year on long-form, or 10M Shorts views/90 days) but not actionable per-video

---

## How to read the retention curve

The retention graph is the most actionable single artifact in YouTube Studio.

Three signatures and what to do about each:

**Cliff at 0:00–0:03**
Viewers swipe away in the first 3 seconds. Hook isn't working.
- Try a different title (A/B from `output/scripts/title_alternatives.md`)
- Try a different opening sentence (different lever: stat-hook vs. role-betrayal vs. action)
- Try a different opening visual

**Cliff at a specific later timestamp**
Viewers stick through the hook, then drop at second N. Something at N is breaking the loop.
- Open the script. Map N to a specific sentence/beat.
- Common offenders: a date-heavy sentence ("From 2018 to 2020…") that loses momentum; a transition between two unrelated beats; a long abstract sentence in a sea of concrete details
- Rewrite that beat in the next case of similar type. Retest.

**Gentle linear decline (no cliff)**
The hook landed and pacing held. This is the healthy curve — you're losing the natural attrition of a 60-second short. The improvement vector here is the CTA at the end: are saves/shares/subscribes high? If not, the outcome beat needs to give viewers a reason to act.

**Negative cliff (curve goes UP)**
This is rare and amazing — means viewers re-watched a section. Usually happens around a surprising fact or a quotable line. Note what was on screen at that second. Replicate that pattern.

---

## Decision rules

Codified "if X then Y" rules so we can automate them later. Initially, run these as a weekly manual review.

### Per-video rules

| Signal | Action |
|---|---|
| 3-sec hold <50% AND CTR <4% | Title is the problem. Re-upload under an alt title from title_alternatives.md after 7-day cooling period. |
| 3-sec hold >70% AND avg view duration <60% | Hook worked but body lost them. Identify the cliff timestamp, rewrite that beat for the next similar-type case. |
| Avg view duration >80% AND likes/views >4% | This is a winner. Make MORE cases in this category. Increase its weight in case selection. |
| Comments per 1K <2 AND subs per video <0.5/1K views | Case may be polished but emotionally cold. Try opening with victim impact instead of defendant action. |
| Dislikes > likes | Case selection error. Pull the video, review what offended, add to filter rules. |

### Per-category rules

After 3+ videos in a category (e.g., "ransomware," "insider trading," "espionage"):

| Signal | Action |
|---|---|
| Category avg retention > overall channel avg + 10pp | Increase category weight in case selector. Aim for 1 in every 3 future cases in this category. |
| Category avg retention < overall channel avg - 10pp | Decrease category weight. May indicate audience doesn't connect with this crime type. |
| Category produces 2x subscriber rate vs. channel avg | This is what builds the channel. Make it the primary lane. |

### Channel-level rules

| Signal | Action |
|---|---|
| 7-day moving avg retention drops 15%+ | Pause new uploads. Run a manual review with this doc. Likely an algorithmic shift or content drift. |
| Comments mention "AI" or "deepfake" without prompting | Audience is detecting the synthetic narration. Consider: switching to a slightly more natural voice (ElevenLabs), or leaning into the AI disclosure as a feature ("All facts verified from public records") |
| Channel passes 1K subs + 10M Shorts views | YPP eligible. Switch descriptions to clickable-URL versions (drop the "no external links" constraint). |

---

## The `analyze_performance.py` future build

A sketch of what the autonomous version looks like once we want to close the loop programmatically.

```python
#!/usr/bin/env python3
"""Pull per-video analytics, score them, and write a weekly review file
that drives case_selector + writer_prompt decisions.

Run as a cron job or `claude` slash command — /weekly-analytics-review.
"""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import date, timedelta
import json, pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTED_PATH = PROJECT_ROOT / "output" / "videos" / "_posted.json"
REPORTS_DIR = PROJECT_ROOT / "reports" / "weekly"

def load_videos_to_review():
    """Read _posted.json, return the videos posted in the last 7 days."""
    posted = json.loads(POSTED_PATH.read_text())
    cutoff = date.today() - timedelta(days=7)
    return [(case_id, m["video_id"]) for case_id, m in posted.items()
            if date.fromisoformat(m["scheduled_publish"][:10]) >= cutoff]

def fetch_metrics(youtube_analytics, video_id):
    """Pull the key metrics. See: developers.google.com/youtube/analytics."""
    resp = youtube_analytics.reports().query(
        ids="channel==MINE",
        startDate="...",  # video publish date
        endDate=str(date.today()),
        metrics=("views,estimatedMinutesWatched,averageViewDuration,"
                 "averageViewPercentage,subscribersGained,subscribersLost,"
                 "likes,dislikes,comments,shares"),
        dimensions="video",
        filters=f"video=={video_id}",
    ).execute()
    return resp["rows"][0]

def fetch_retention_curve(youtube_analytics, video_id):
    """Per-second retention. Use the audienceRetentionPercentage metric."""
    resp = youtube_analytics.reports().query(
        ids="channel==MINE",
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
    ).execute()
    return resp["rows"]

def score_video(metrics, retention):
    """Apply Tier-1 rules from the strategy doc."""
    three_sec_hold = retention_at(retention, 0.05)  # 5% of 60s ≈ 3s
    avg_view_pct = metrics["averageViewPercentage"]
    ctr = ... # views / impressions (need Studio scrape or another query)
    likes_ratio = metrics["likes"] / max(metrics["views"], 1)

    flags = []
    if three_sec_hold < 0.5 and ctr < 0.04:
        flags.append("title_is_problem")
    if three_sec_hold > 0.7 and avg_view_pct < 60:
        flags.append("body_loses_them")
    if avg_view_pct > 80 and likes_ratio > 0.04:
        flags.append("winner_category")
    # ... etc.
    return flags

def category_of(case_id):
    """Tag case by category for cross-video aggregation."""
    if "ransomware" in case_id: return "cyber"
    if "espionage" in case_id: return "national_security"
    if "insider" in case_id: return "white_collar"
    # ... etc.
    return "other"

def main():
    creds = Credentials.from_authorized_user_file(str(PROJECT_ROOT / "token.json"),
                                                  ["https://www.googleapis.com/auth/yt-analytics.readonly"])
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    by_category = {}
    per_video = []
    for case_id, video_id in load_videos_to_review():
        metrics = fetch_metrics(youtube_analytics, video_id)
        retention = fetch_retention_curve(youtube_analytics, video_id)
        flags = score_video(metrics, retention)
        per_video.append({"case_id": case_id, "metrics": metrics, "flags": flags})
        by_category.setdefault(category_of(case_id), []).append(metrics)

    # Aggregate category scores; write feedback into case_selector_weights.json
    weights = compute_category_weights(by_category)
    (PROJECT_ROOT / "skill" / "truecrime-short" / "case_selector_weights.json").write_text(
        json.dumps(weights, indent=2))

    # Write the weekly review report
    report = build_report(per_video, by_category, weights)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{date.today().isoformat()}.md").write_text(report)
```

The two outputs that close the loop:

1. **`case_selector_weights.json`** — the selector reads this on each Phase 0 run and biases case selection toward categories with strong retention. After 30+ videos this becomes a real signal.

2. **Weekly markdown report** at `reports/weekly/<date>.md` — human-readable summary with: top performer, bottom performer, retention curve flags per video, category rollup, recommended writer-prompt adjustments. Drop this in chat or have Claude Code read it on `/weekly-review`.

---

## Rollout schedule

**Days 1–14 (after case 01 goes live)** — All decisions manual. Open Studio every 2 days, eyeball the retention curve, note observations in a single `reports/weekly/observations.md`. Don't make changes yet — we need ~5 videos worth of data to distinguish signal from noise.

**Days 15–30** — First real review. With ~5 videos live, look for category patterns. Pick one or two writer-prompt adjustments based on what's working. Update the prompt, run cases #07–#08 against the new version, watch for delta.

**Days 31–60** — Build `analyze_performance.py` as described above. Run weekly. Start auto-adjusting case-selector weights. Continue manual prompt iteration.

**Day 60+** — Pipeline is mostly closed-loop. Manual reviews shift from weekly to monthly. New experiments (long-form companion content, alternative narrators, etc.) come from the data, not intuition.

---

## What we won't optimize for (yet)

These are tempting metrics that don't yet matter for our stage:

- **RPM / ad revenue per video** — we can't be monetized until YPP eligibility. Watch the trend, don't chase it.
- **Average time-to-publish** — every Short is cheap to render, so producing more is rarely the answer; producing *better* is.
- **Subscriber count as a goal** — subs are a downstream consequence of good content. Optimize the upstream metrics (retention, CTR) and subs follow.
- **Comment sentiment** — we'll get plenty of "fake news" / "AI slop" comments regardless of quality. Don't let the loudest commenters drive decisions; use aggregate metrics.

---

## The single most important insight

For the first 60 days, the only retention metric that materially matters is the **3-second hold**. If you make the hook work, everything else (CTR, watch time, subscriber conversion) follows. If you don't make the hook work, no amount of script polish or scene quality matters because no one sees it.

When in doubt: cut a second from the hook, add a more specific number, lead with the most counter-intuitive juxtaposition the case offers. Then test.
