# Niche Playbook

Per-vertical production templates: voice picks, hook templates, visual style, 4-beat script structure, fair-use rules. Use this as the daily reference when prepping a new video for any niche.

---

## Common structure (all niches)

Every video uses the same 4-beat skeleton:
- **Beat 1 — Hook** (10-15s): pattern interrupt + curiosity gap
- **Beat 2 — Setup/Gameplay** (12-15s): the core mechanic, story, or context
- **Beat 3 — Standout** (12-15s): why this matters / surprising twist
- **Beat 4 — CTA** (5-10s): release date, platform, "follow for more X"

Total narration target: **120-140 words** for a 45-55s short.

---

## Niche 1 — Games (current, established)

| Field | Value |
|---|---|
| ID prefix | `GG_NN_<slug>` |
| Voice rotation | Adam / Charlie / Callum (queue_number % 3) |
| Model | `eleven_turbo_v2` (high-energy) |
| Visual source | YouTube official trailer via `fetch_trailer.py` → 4 scene-extracted clips |
| Crop strategy | `pillarbox_blur` (default — preserves trailer content) |
| Description footer | None — game trailers are publisher-released for sharing |

### Hook templates that work for games
- **Authority:** "From the makers of [legendary franchise] — [new game] does [unique mechanic]"
- **Stat:** "[Studio] spent N years building this. M players bought it in the first month."
- **Premise:** "[Game name] has been delayed N times. Here's what changed."

---

## Niche 2 — Court cases / True crime

| Field | Value |
|---|---|
| ID prefix | `NN_<slug>` (numeric, e.g. `01_gothferrari`) |
| Voice | **Brian** (`nPczCjzI2devNBz1zQrb`) — narrator authoritative |
| Model | `eleven_multilingual_v2` (slower documentary tone) |
| Visual source | AI/stock via `build_visuals_track.py` — courtroom imagery, evidence shots, mugshots when public |
| Crop strategy | `pillarbox_blur` for any 16:9 source |
| Description footer | "Sources cited in description. All visuals AI-generated or stock; not depicting real persons." |

### Hook templates that work for crime
- **Stat:** "$67 million stolen. 3 arrests. 1 fugitive."
- **Setup:** "She drove the Goth Ferrari. He drove the getaway."
- **Mystery:** "The genetic-testing fraud no one saw coming."

### Compliance
- Never name minors involved in cases
- Stick to publicly-reported facts
- Cite court records or news sources in the description

---

## Niche 3 — Movies (planned, Week 1)

| Field | Value |
|---|---|
| ID prefix | `MV_NN_<slug>` |
| Voice rotation | Adam / Charlie / Callum (same A/B as games) |
| Model | `eleven_turbo_v2` |
| Visual source | Official movie trailer from studio YouTube channel |
| Crop strategy | `pillarbox_blur` |
| Description footer | "Trailer footage © [Studio]. Used under fair-use commentary; narration original." |

### Hook templates
- **Studio + premise:** "Apple Studios is making a film about [unusual topic]."
- **Cast + twist:** "[Star A] and [Star B] are in a [genre] from [acclaimed director]."
- **Anticipation:** "[Director]'s next movie just dropped its first trailer. Here's what it's about."

### Fair use rules
- Max 28s of source trailer footage per video (≤7s per clip × 4 clips)
- Original narration provides the transformative commentary
- Always include the fair-use footer in description

---

## Niche 4 — Personal Finance / Money Hacks (planned, Week 2)

| Field | Value |
|---|---|
| ID prefix | `FN_NN_<slug>` |
| Voice | **Daniel** (`onwK4e9ZLuTAKqWW03F9`) — British formal, finance/news tone |
| Model | `eleven_multilingual_v2` |
| Visual source | Stock charts + AI-generated abstract money imagery + screen recordings of finance apps |
| Crop strategy | Generate 9:16 directly; `pillarbox_blur` for any 16:9 stock |
| Description footer | "Educational content only — not financial advice. Consult a licensed advisor for personal decisions." |

### Hook templates
- **Stat:** "Americans lose $X per year to one credit card mistake."
- **Contradiction:** "Cheap insurance isn't real — here's why."
- **Specificity:** "3 ways your 401k match is leaving money on the table."
- **Personal:** "I switched from [X bank] to [Y bank] and got back $N."

### Compliance landmines
- Never recommend specific stocks or crypto
- Always frame as "educational" / "informational"
- Avoid "guaranteed returns" or "get-rich-quick" language
- Affiliate disclosure mandatory on every video that includes a partner link

---

## Niche 5 — Top X Rankings (planned, Week 3)

| Field | Value |
|---|---|
| ID prefix | `TX_NN_<slug>` |
| Voice | Charlie (conversational rankings) |
| Model | `eleven_turbo_v2` |
| Visual source | Per-item AI/stock images via `build_visuals_track.py` (5 images per video, one per ranked item) |
| Crop strategy | `pillarbox_blur` per item image |
| Description footer | None (original commentary throughout) |

### Hook templates
- **Countdown energy:** "Top 5 [X] of 2026. Number 3 will surprise you."
- **Authority:** "Ranked by [credible source / metric] — the 5 most [X] [Y]."
- **Curated edge:** "Every [X] under [threshold] you should know about, ranked."

### Format notes
- Beat 1: Hook + tease number 1 (without revealing)
- Beat 2: Position #5 → #4
- Beat 3: Position #3 → #2
- Beat 4: Position #1 + CTA
- On-screen ranking counter (5/5, 4/5, etc.) shown on each beat

---

## Niche 6 — Mythology / History Explainers (planned, Week 4)

| Field | Value |
|---|---|
| ID prefix | `MY_NN_<slug>` (Mythology) or `HI_NN_<slug>` (History) |
| Voice | Brian or Rachel — both work; A/B test |
| Model | `eleven_multilingual_v2` |
| Visual source | AI-generated mythological art (Flux 2 Pro when budget approved) + public-domain paintings (Wikimedia Commons) |
| Crop strategy | Generate at 9:16; `pillarbox_blur` for landscape paintings |
| Description footer | "Art sources: AI-generated and public-domain (Wikimedia Commons / [specific museum])." |

### Hook templates
- **Surprising fact:** "Norse mythology had a god of poetry — and he started a war over honey."
- **Origin reveal:** "Before Zeus killed his father, his father did something worse."
- **Comparison:** "Greek mythology has one god of war. Norse has three."

### Compliance
- Religious content (Bible stories, Quran-based) — handle carefully; safer to stick to Greek/Norse/Egyptian/Celtic mythology where there's no active religious community
- AI-generated art clearly marked in description

---

## Niche 7 — Unsolved Mysteries / Conspiracies (planned, Week 4)

| Field | Value |
|---|---|
| ID prefix | `UM_NN_<slug>` |
| Voice | Brian (dramatic suspense tone) |
| Model | `eleven_multilingual_v2` |
| Visual source | AI/stock — archival-style photography + atmospheric AI imagery + Ken Burns motion |
| Crop strategy | `pillarbox_blur` |
| Description footer | "All theories presented are speculative. Sources cited where available." |

### Hook templates
- **Mystery setup:** "A passenger flight vanished over the Pacific in 1987. Then in 2024, it was found."
- **Unexplained event:** "47 people heard the same sound at exactly the same time."
- **Cold case angle:** "She left her car running and was never seen again."

### Compliance
- Never accuse named living persons of crimes
- Label speculative content clearly
- Avoid harmful conspiracy theories (election denial, vaccine misinformation, holocaust denial — these will get the channel demonetized)

---

## Niche 8 — Psychology Facts / Mind Hacks (planned, Month 2)

| Field | Value |
|---|---|
| ID prefix | `PS_NN_<slug>` |
| Voice | Rachel (warm authoritative — research-backed psychology) |
| Model | `eleven_multilingual_v2` |
| Visual source | Stock + simple AI-generated brain/mind imagery; minimal text overlays |
| Crop strategy | `pillarbox_blur` |
| Description footer | "Educational content; not medical or mental health advice." |

### Hook templates
- **Reframe:** "You're not lazy. You're avoiding dopamine debt."
- **Counterintuitive:** "The IKEA effect — why you'll defend a bookshelf you built badly."
- **Research-backed:** "Stanford studied 1,000 couples. The ones that lasted did this one thing."

### Compliance
- Always research-backed (cite the study in description when possible)
- No mental health diagnostics or treatment claims
- Avoid suicide / self-harm topics

---

## Niche 9 — AI Tool Tutorials / Reviews (planned, Month 2)

| Field | Value |
|---|---|
| ID prefix | `AI_NN_<slug>` |
| Voice | Charlie (conversational, modern tone) |
| Model | `eleven_turbo_v2` |
| Visual source | Screen recordings of AI tool interfaces + stock B-roll cuts (Pipeline 3 — defer until Tier 1 proves out) |
| Crop strategy | `pillarbox_blur` for landscape screen recordings |
| Description footer | Affiliate disclosure if tool has affiliate program |

### Hook templates
- **Time-savings:** "I replaced [X expensive task] with [Y AI tool] in 60 seconds."
- **Stack reveal:** "5 AI tools I use every day. #3 is free."
- **Comparison:** "ChatGPT vs Claude vs Gemini — which one writes the best [Y]?"

### Compliance
- Always disclose affiliate relationships
- Don't make false performance claims about tools
- Mark AI-generated content clearly

---

## Voice-to-niche quick reference

| Voice | Niches |
|---|---|
| Adam | Games, gaming hype |
| Charlie | Top X, AI tools, general conversational |
| Callum | Sports highlights, energetic gaming |
| Brian | Cases, mysteries, history, mythology |
| Rachel | Psychology, self-improvement, soft authority |
| Daniel | Finance, news, formal authority |

---

## Hook template registry (cross-niche)

| Hook style | Best for | Example |
|---|---|---|
| **Stat** | Cases, Finance, Games | "$67M stolen. 3 arrests. 1 fugitive." |
| **Authority** | Games, Movies, AI tools | "From the team that built Halo and Destiny..." |
| **Curiosity** | Mysteries, Psychology | "A passenger flight vanished in 1987..." |
| **Contradiction** | Finance, Psychology | "Cheap insurance isn't real — here's why" |
| **List tease** | Top X, Rankings | "5 [X] of 2026. Number 3 will surprise you." |
| **Reframe** | Psychology, Self-improvement | "You're not lazy. You're avoiding dopamine debt." |
| **Premise** | Games, Mythology | "Norse had a god of poetry — and he started a war over honey." |

Track which hook style wins per niche via the experiment ledger.
