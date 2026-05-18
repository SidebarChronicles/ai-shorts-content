# Monetization (v2 — May 18 2026)

> **Honest current state:** $0 revenue, ~$82/mo costs (EL $22 + Replicate ~$45 + PostFast ~$15). Realistic break-even = 60-90 days. Channel is in pre-revenue "research budget" mode until Phase 4.

## Why no affiliate links

We explored TikTok Shop affiliate + Amazon Associates in earlier iterations. **Confirmed bad fit for AI-narrative shorts.** The videos are 40-50s narrative stories (POV survival, Reddit dramatizations, horror). They don't naturally feature products. Forcing "🔗 my survival kit on Amazon" into a survival POV breaks immersion and signals "this is an ad" — which tanks the retention we're trying to build.

Affiliate-led monetization works for product-demo content (unboxings, "I bought this on TikTok"), not narrative content. We dropped that path.

## What we DO monetize on (in priority order)

| Path | Threshold to unlock | Realistic timeline | Expected $/month at threshold |
|---|---|---|---|
| **TikTok Creator Rewards Program** | 10K followers + 100K views/30d | 30-60 days | $30-170 |
| **YouTube Shorts AdSense (YPP)** | 1K subs + 10M Shorts views/90d | 90-180+ days | $60-300+ |
| **YouTube YPP Early Access** | 500 subs + 3M Shorts views/90d | 90+ days | $30-100 |
| **Brand sponsorships (DM-driven)** | 5K+ followers in clear niche | 60-120 days | $50-500/deal, variable |
| **Patreon / Ko-fi** | 500-1K engaged fans | 60-90 days | $5-20/supporter × N |
| **Compilation channel revenue share** | Standout individual videos | 90+ days | Variable |

All paths are **follower-driven**, not click-driven. That's why every video's CTA in v2 explicitly drives FOLLOWS:

> Survival: "Day N+1 drops tomorrow — **follow so you don't miss it.**"
> Horror: "Don't [verb] [object]. **Follow if you want more.**"
> Reddit: "AITA? **Comment your verdict. Follow for daily AITAs.**"

## Tracking

Daily cost is auto-tracked by `output/elevenlabs_usage.json` + `output/replicate_usage.json`.

Manual revenue entry once monetization unlocks:
```bash
# Once Creator Rewards starts paying out:
python3 scripts/revenue_tracker.py --add tiktok_creator_rewards 12.50
python3 scripts/revenue_tracker.py --add youtube_adsense 5.00
python3 scripts/revenue_tracker.py --add brand_deal 250.00 --note "Audible sponsorship"

# Monthly summary:
python3 scripts/revenue_tracker.py --monthly

# Cost vs revenue break-even check:
python3 scripts/revenue_tracker.py --break-even-check
```

## YouTube AdSense compliance (still applies under v2)

- ✅ AI-narration disclosure ("⚠ Narration in this video is AI-generated (ElevenLabs)") in every YouTube description
- ✅ Music attribution ("🎵 Music: Kevin MacLeod — CC-BY 4.0") in every description
- ✅ No reused content from other channels (all our scripts + visuals are original)
- ✅ Original prose on Reddit dramatizations (no verbatim copying — see `docs/AI_STORIES_PLAYBOOK.md` § anti-plagiarism)
- ✅ AI-content toggle enabled in YouTube Studio uploads (set per-video via API)

Under YouTube's January 2026 "inauthentic content" enforcement: we're protected because (1) original scripts per video, (2) production variation across sub-genres, (3) reasonable cadence (8/day max, well below the 12+/day bot threshold), (4) human editorial review at phase transitions.

## TikTok AI-content compliance

TikTok requires the "AI-generated content" toggle on AI-narrated videos (since 2024). Set this manually per upload from the mobile app: More options → toggle "AI-generated content" ON. Skipping it can result in shadow-banning.

## Cost ceiling (auto-guard)

- ElevenLabs Creator tier: $22/mo (90k char soft-cap in `.channel_phase.json`)
- Replicate: ~$45/mo projected at 8/day cadence (no hard cap; user-set $40 limit in Replicate dashboard recommended)
- PostFast scheduler: ~$15/mo (autonomous TT + IG Reels cross-poster — see `docs/CROSS_POSTING.md`)
- **Combined target: ≤$100/mo until break-even**

If costs trend past $100/mo without proportional revenue, options (in order of reversibility):
1. Reduce production to 6/day (drop one fire) — saves ~$11/mo on Replicate.
2. Cancel PostFast and revert to manual cross-post — saves $15/mo, costs ~24 min/day of finger-work.
3. Trim Phase 1 vertical pool to the 2-3 strongest.

All reversible.

## When monetization unlocks — what to do

**Day 30-60 (TikTok Creator Rewards eligibility):**
1. Check follower + 30d view count via TikTok Studio
2. Apply at https://www.tiktok.com/creator-academy/en/creator-rewards-program if eligible
3. Approval typically within 7 days
4. First payout ~30 days after approval

**Day 90+ (YouTube YPP eligibility):**
1. Check sub count + 90d Shorts views in YouTube Studio
2. Apply via Studio → Monetization
3. Review can take 1-30 days
4. First AdSense payment when account reaches $100 threshold

**Day 60+ (Brand deals, if niche traction):**
1. Add "📧 [email] for brand inquiries" to TikTok + IG bios
2. Maintain a one-pager media kit (channel niche, follower count, avg views, demographics)
3. Respond to inbound DMs within 24h to maintain seriousness signal
