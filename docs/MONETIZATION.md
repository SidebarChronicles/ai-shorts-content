# Monetization Playbook

The single-page reference for getting this channel sustainably profitable. Read top-to-bottom once, then check the weekly + monthly action sections regularly.

---

## YouTube Partner Program thresholds (2026)

YouTube splits YPP into two tiers:

| Tier | Subscribers | Watch hours OR Shorts views | Unlocks |
|---|---|---|---|
| **Early Access (fan funding)** | 500 | 3,000 watch hrs **OR** 3M Shorts views in 90d | Super Thanks, Super Chat, channel memberships |
| **Full YPP (ad revenue)** | 1,000 | 4,000 watch hrs **OR** 10M Shorts views in 90d | Ad revenue + everything above |

Channel must also have 2-step verification, advanced features, and an AdSense account.

**Shorts ad revenue share:** Creator pool gets ~45% of attributed Shorts ad revenue, then split by share of engaged views. Music licensing eats 50% per track used (use ≤1 track and pick royalty-free).

---

## Reuse policy compliance (the demonetization landmine)

YouTube renamed "Repetitious Content" → **"Inauthentic Content"** in July 2025 with enhanced detection. AI is fine; mass-produced templates aren't.

### What's allowed
- AI narration (ElevenLabs TTS) reading **original** scripts
- AI-generated visuals
- Trailers / clips from sources we have license to use (publisher-released game trailers, movie trailers from studio channels)
- Stock images + Ken Burns motion
- "Top X" lists where each item gets original commentary

### What's NOT allowed (demonetization risk)
- Raw uploads of someone else's video with TTS slapped over it
- Identical-template videos churned at high volume (e.g., 50 videos using the same beat structure, same intro/outro, same visual style with only the topic swapped)
- AI-generated voices impersonating specific real people
- Copyright-claimed footage used beyond fair-use thresholds (typically <30s with substantial transformative commentary)

### Compliance levers we ship with
| Lever | Where |
|---|---|
| Synthetic-content disclosure | `upload_to_youtube.py` sets this on every upload |
| Original 4-beat scripts | Each video has its own hook/setup/standout/CTA — not template-filled |
| Multiple verticals | Diversity protects against "this looks like a content farm" flags |
| Per-vertical voice + visual style | Different ElevenLabs voices per niche reduce template signature |

### Periodic compliance check (run weekly)
1. Open YouTube Studio → Monetization
2. Check for "Yellow $" icons (limited monetization) — investigate per video
3. Check Copyright tab for any new claims
4. Confirm the "Made for kids: False" flag is still set on every upload
5. Check Channel violations under Settings → Channel → Advanced

---

## Affiliate program enrollment

Week 1 priority — apply for all of these. Most approve in 7-14 days.

| Program | Niches | Typical payout | Apply |
|---|---|---|---|
| Amazon Associates | Books, products mentioned in any vertical | 1-10% commission | [amazon.com/associates](https://affiliate-program.amazon.com/) |
| Steam Curator Partner | Games | Wishlist credit only (no direct $) | [partner.steamgames.com](https://partner.steamgames.com/) |
| Skillshare | Self-improvement, psychology, AI tools | $7/free trial + 30% recurring | [skillshare.com/affiliate](https://www.skillshare.com/affiliate) |
| Brilliant | Psychology, science, math content | $30/sign-up | brilliant.org affiliate page |
| ShareASale (master account) | Software, finance | Varies $30-$300 CPA | [shareasale.com](https://shareasale.com) |
| Impact.com | Software, SaaS, fashion | Varies | [impact.com](https://impact.com) |

### Higher-tier programs (apply after 1k subs)
- **NordVPN / Surfshark / ProtonVPN** — $30-100 CPA for tech/AI vertical
- **Webull / Public / Robinhood** — $50-150 CPL for finance vertical
- **Coursera / MasterClass** — recurring revenue share

### Description-template for monetized videos
After hitting affiliates, every video description should include:
- 1-2 contextual affiliate links (the product/book/service mentioned in the video)
- Channel social links
- Hashtags
- Synthetic-content disclosure note

---

## Revenue projection (Conservative path)

Assumes Tier 1 niche expansion (Finance, Top X, Mythology, Mysteries) ships in May-June 2026 and adds 4 new videos/day on average to existing game + case output.

| Phase | Month | Subs | 90d Shorts views | Monthly ad rev | Affiliate | Sponsor | Monthly total |
|---|---|---|---|---|---|---|---|
| Phase 0 | May 2026 | 0-100 | 0-200k | $0 | $0 | $0 | $0 |
| Phase 1 (Early YPP) | Jun 2026 | 500-1k | 1-3M | $0 (under full YPP) | $20-50 | $0 | ~$30 |
| Phase 2 (Full YPP) | Jul 2026 | 1k-3k | 5-10M | $200-600 | $50-200 | $0 | ~$500 |
| Phase 3 (Growth) | Aug 2026 | 3k-10k | 10-15M | $500-2,000 | $200-500 | $0-500 | ~$2,000 |
| Phase 4 (Sponsorship) | Oct 2026 | 25k-50k | 15-30M | $2k-5k | $500-2k | $500-3k | ~$8,000 |
| Phase 5 (Sustainability) | Q1 2027 | 100k+ | 30M+ | $5k-15k | $2k-5k | $3k-15k | ~$20,000+ |

**Worst-case:** subtract 60% across the board if niches don't hit retention targets.

---

## Sponsorship outreach (Week 4 onward)

### Rate card per subscriber tier
| Subs | Per-Shorts segment | Caveats |
|---|---|---|
| 10k | $500-2,000 | Sponsors typical discount 20-30% for faceless channels |
| 100k | $1,000-5,000 | |
| 1M+ | $10,000-50,000+ | |

### Outreach email template (to be drafted Week 4)
Pitch should include:
- Channel link + niche fit
- Top 3 video views/retention metrics
- Audience demographics (when YouTube Studio surfaces it post-1k subs)
- Proposed video integration format
- Pricing tier (start mid-range, leave room to negotiate)

---

## Monthly review checklist (run on the 1st of each month)

- [ ] YPP eligibility tracker — distance from 500/3M (early) or 1k/10M (full)
- [ ] Per-vertical RPM table — which is highest? Which is lowest?
- [ ] Voice leaderboard — Adam vs Brian vs Daniel etc. — clear winner?
- [ ] Niche commitment decisions — any niche that hit <50% of G2 targets after 10 videos should be cut
- [ ] Affiliate revenue per program — any underperformers to drop?
- [ ] New affiliate programs to apply to (based on top-performing niche)
- [ ] Sponsor outreach queue (post-10k subs)
- [ ] Compliance check — any new copyright claims or limited-monetization icons?

---

## Quick-reference revenue math

- **Shorts RPM benchmarks:** Finance $5-15, Psychology $7-13, AI Tools $3-9, Mythology $4-8, Mysteries $3-6, Top X $2-5, Movies $2-4, Games/Crime $0.03-0.12
- **1M Shorts views at $0.10 RPM** = $100
- **1M Shorts views at $5 RPM** = $5,000
- **One $200 affiliate sale** = equivalent to ~2M Shorts views at the average gaming/crime RPM
- **One $1k sponsorship** = equivalent to ~10M Shorts views at gaming RPM

The math is brutal for gaming/crime alone. Affiliates and sponsors are how the channel becomes profitable below 1M monthly views.
