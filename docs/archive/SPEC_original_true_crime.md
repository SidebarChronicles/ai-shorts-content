# True Crime Shorts — Autonomous Pipeline Spec

> Paste this entire file into Claude Code as your opening message.
> Run: `claude` inside your project folder, then paste.

---

## Project overview

Build a fully autonomous Python pipeline that ingests true-crime source material from public legal and journalistic records, generates a fact-grounded short script with inline citations, verifies every claim against the source documents, renders a 45–55 second vertical video with layered b-roll and word-level captions, and uploads it as a scheduled YouTube Short via the YouTube Data API v3 — all triggered by a cron job with zero manual intervention after setup.

**Target output:** 1 video/day for the first 60 days (algorithm-friendly ramp), then optionally 2/day. ~45–55 seconds each, vertical 1080×1920, scheduled across the week.

---

## Build strategy

This spec describes the fully autonomous destination. We are **not** building all of it in one pass — the autonomous system has too many failure modes to commit to before validating that the *content itself* finds an audience.

### Tiered MVP path

| Tier | What it includes | Validates |
|---|---|---|
| 1 | Scripts only (Claude writes + verifies in chat) | Writer prompt produces compelling scripts |
| **2 ← we are here** | Scripts + finished mp4 rendered in-session, **manual upload** | Full creative output performs on the platform |
| 3 | Packaged as a `/truecrime` skill for one-command invocation | Workflow ergonomics |
| 4 | Full autonomous: droplet, cron, OAuth uploader, alerting | Scale past manual capacity |

### Phase flow (Tier 2)

0. **Research** — Claude pulls 6–8 candidate cases from sources, scores them, presents a shortlist
1. **Selection** — Justin picks one case
2. **Deep research** — Claude pulls all source documents for the chosen case and builds the RAG context
3. **Script** — Writer pass with inline citations → verifier pass (every claim must map to a source quote) → safety classifier
4. **Approval** — Justin reviews script, requests edits or approves
5. **Assembly** — TTS → word-level timing → ASS subtitle file → Pexels stock + rendered overlays → FFmpeg one-pass render
6. **Delivery** — Finished mp4 + metadata sidecar (title, description, AI disclosure reminder, source attribution) dropped in the project folder

### Decisions captured so far

- **Niche:** True crime — survives the January 2026 demonetization wave better than Reddit-stories format and pays $4–10 RPM with exceptional watch-time
- **Upload (Tier 4):** YouTube Data API v3 with OAuth refresh token, *not* Playwright on YouTube Studio
- **Captions:** FFmpeg + libass via ASS subtitle file, *not* MoviePy per-word TextClips (memory + reliability)
- **Source rotation:** DOJ press releases (convictions only) + CourtListener federal opinions + Chronicling America historical (pre-1928)
- **Content filter:** Skip cases involving minors, sexual violence, and ongoing investigations
- **Editorial guardrail:** Every factual claim must cite a source quote; verifier pass fails the job on any unsupported claim
- **AI disclosure:** YouTube `containsSyntheticMedia: true` set on every upload (synthetic narration triggers required disclosure under the May 2025 policy)
- **No AI faces of real people, ever** — likeness + defamation risk

### Graduation criteria

- **Tier 2 → 3:** After ~5 videos in the same flow with consistent quality (scripts passing verification, Justin approving without major edits, retention signal coming back from YouTube)
- **Tier 3 → 4:** After 20–30 videos with subscriber growth signal, when manual upload becomes the bottleneck

---

### Why true crime, and why this architecture

True-crime narration has held up well through YouTube's January 2026 "AI slop" enforcement wave: RPMs are $4–10, watch-time per session is exceptional, and the format monetizes ~40% faster than lifestyle content. But two failure modes are channel-killers in this space:

1. **Fabrication.** "True Crime Case Files" (83K subs) was terminated for posting 150+ AI-generated *fictional* cases presented as real. The pipeline must never invent facts.
2. **Defamation and likeness.** Naming uncharged suspects, speculating on guilt, or generating AI faces of real people invites takedowns and legal exposure.

The architecture defends against both by construction: every script is a **retrieval-augmented generation** over source documents the pipeline pulled itself; a second LLM pass verifies each factual claim maps to a citation in those sources; a safety filter blocks defamation patterns and graphic content; and the visual layer uses only public-record materials, generic stock, animated maps, and abstract AI imagery that contains no real people.

---

## Hosting

**Platform:** DigitalOcean Basic Droplet
**Plan:** 1 vCPU, 2GB RAM, 50GB SSD — $12/month
**OS:** Ubuntu 24.04 LTS
**Region:** Pick closest to your location (e.g. NYC1, LON1)

New DigitalOcean accounts receive $200 free credit valid for 60 days — enough to cover the first ~16 months of this droplet at no cost during the trial period.

### Why this spec

- 2GB RAM is comfortable now that the composer uses direct FFmpeg + `libass` instead of MoviePy. The earlier MoviePy + per-word TextClip design would have OOM'd; this one renders in a single FFmpeg pass with subtitles burned from an ASS file.
- 50GB SSD comfortably holds the pipeline codebase, cached stock footage, rendered scene PNGs, SQLite database, and temporary render files with plenty of room.
- **No persistent Chromium profile is required** because uploads use the YouTube Data API v3 with an OAuth refresh token — the spec is unchanged on serverless platforms in principle, but cron + a small VM is still the simplest deployment.

### Server setup (run once after creating the Droplet)

```bash
# 1. SSH in
ssh root@YOUR_DROPLET_IP

# 2. Set timezone explicitly — cron uses droplet local time
timedatectl set-timezone America/New_York   # or your TZ

# 3. System dependencies
apt update && apt upgrade -y
apt install -y python3-pip python3-venv ffmpeg git fonts-noto-core libass9

# 4. Clone project and install Python deps
git clone YOUR_REPO_URL && cd true-crime-shorts-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Copy and fill in secrets
cp .env.example .env
nano .env   # paste your API keys

# 6. One-time YouTube OAuth (must be done once, locally is easier)
python scripts/youtube_oauth.py
# This opens a browser, you grant consent, the script writes
# token.json which contains a long-lived refresh token.
# scp token.json up to the droplet:
#   scp token.json root@YOUR_DROPLET_IP:~/true-crime-shorts-bot/

# 7. Cache a starter stock library (run once, ~500MB)
python scripts/seed_stock_assets.py

# 8. Test the pipeline without uploading
python main.py --dry-run

# 9. Set up cron (runs once at 10am local time daily)
crontab -e
# Add these lines (note: TZ inherits from system after step 2):
# 0 10 * * * /root/true-crime-shorts-bot/venv/bin/python /root/true-crime-shorts-bot/main.py >> /root/true-crime-shorts-bot/logs/cron.log 2>&1
```

### Monitoring

```bash
tail -f ~/true-crime-shorts-bot/logs/pipeline.log   # live log
grep "FAILED" ~/true-crime-shorts-bot/logs/pipeline.log
grep "COMPLETE" ~/true-crime-shorts-bot/logs/pipeline.log | tail -20
grep "SAFETY_BLOCK" ~/true-crime-shorts-bot/logs/pipeline.log  # filter trips
```

For autonomous operation you want at minimum a failure ping. The pipeline calls `alert.notify_failure(...)` on terminal errors — wire that to a free Healthchecks.io ping URL or an SMTP send. See `pipeline/alert.py`.

---

## Tech stack

| Layer | Tool | Notes |
|---|---|---|
| Hosting | DigitalOcean Basic Droplet (2GB RAM) | Ubuntu 24.04, $12/mo |
| Sources | CourtListener API, DOJ press RSS, Chronicling America | All free, all public record |
| Case selection | Custom scorer | Length, recency, sensitivity score |
| RAG context | Sentence chunking, simple BM25 retrieval | No vector DB needed at this scale |
| Script writing | OpenAI GPT-4o-mini (writer + verifier passes) | Cheap, fast, structured output |
| Safety filter | Rules + GPT-4o-mini classifier | Defamation, graphic content, sensitivity |
| TTS | Kokoro TTS (local) or ElevenLabs API | Kokoro for trial; ElevenLabs alignment skips whisper |
| Caption timing | faster-whisper (Kokoro path only) | Word-level timestamps, no API cost |
| Stock footage | Pexels API (cached locally) | Royalty-free, attribution optional |
| Doc/map renders | Playwright headless → PNG | Render HTML templates of court docs, Mapbox-style maps |
| Newspaper clippings | Chronicling America (LoC) | Pre-1928 = fully public domain |
| Video composition | FFmpeg + libass (ASS subtitle file) | Single pass, ~10x less RAM than MoviePy |
| Upload | YouTube Data API v3 + OAuth refresh token | Scheduled private→public via `status.publishAt` |
| AI disclosure | API flag set per upload | Required for synthetic narration |
| Job tracking | SQLite | Dedup, queue, idempotent upload state |
| Orchestration | Python + cron | 1×/day on VPS |
| Config | `config.yaml` + `.env` | All secrets and settings external |
| Logging | Python `logging` → `/logs/pipeline.log` | Rotating, 7-day retention |
| Alerting | `pipeline/alert.py` → Healthchecks.io or SMTP | Pings on terminal failure |

---

## Directory structure

```
true-crime-shorts-bot/
├── main.py                       # Orchestrator — entry point for cron
├── config.yaml                   # All user-configurable settings
├── .env                          # API keys (never committed)
├── .env.example
├── requirements.txt
├── README.md
├── token.json                    # OAuth refresh token (gitignored)
│
├── scripts/
│   ├── youtube_oauth.py          # One-time OAuth consent flow
│   └── seed_stock_assets.py      # Pre-download starter stock library
│
├── sources/
│   ├── base.py                   # BaseSource abstract class
│   ├── courtlistener.py          # Federal/state court opinions + dockets
│   ├── doj_press.py              # DOJ press release RSS
│   └── chronicling_america.py    # Public domain historical (pre-1928)
│
├── pipeline/
│   ├── selector.py               # Case selection + dedup + sensitivity scoring
│   ├── rag.py                    # Source chunking + retrieval
│   ├── writer.py                 # Script generation with inline citations
│   ├── verifier.py               # Second-pass fact check against sources
│   ├── safety.py                 # Defamation + graphic content filter
│   ├── tts.py                    # TTS audio generation (Kokoro or ElevenLabs)
│   ├── captions.py               # Word timestamps → ASS subtitle file
│   ├── scene_planner.py          # Plan which visuals appear when
│   ├── assets.py                 # Pexels fetch, doc render, map render, newspaper render
│   ├── composer.py               # FFmpeg one-pass composition
│   ├── uploader.py               # YouTube Data API v3 upload + schedule
│   └── alert.py                  # Failure notifications (Healthchecks/SMTP)
│
├── db/
│   └── database.py               # SQLite helpers
│
├── assets/
│   ├── stock/                    # Cached Pexels clips
│   ├── fonts/                    # Bundled fonts for ASS rendering
│   └── templates/                # HTML/CSS templates for doc + map renders
│
├── output/
│   ├── sources/                  # Raw source documents per case (kept for audit)
│   ├── scripts/                  # Generated scripts + citation maps
│   ├── audio/                    # Generated .mp3 files (auto-purged after render)
│   ├── captions/                 # ASS subtitle files
│   ├── scenes/                   # Rendered scene PNGs
│   └── videos/                   # Final rendered .mp4 (auto-purged after upload)
│
└── logs/
    └── pipeline.log
```

---

## Source adapter pattern

Every source must extend `BaseSource` and implement `fetch()`. The contract is one method — the rest of the pipeline never imports source-specific code.

```python
# sources/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SourceQuote:
    """A retrievable excerpt from the source. The RAG and verifier
    layers operate over these — the script can only assert facts that
    map to a SourceQuote."""
    text: str
    cite_id: str        # e.g. 'docket_p3_para2', used in script citations

@dataclass
class CaseItem:
    title: str           # human-readable case title
    summary: str         # 1-3 sentence summary for selection scoring
    body: str            # full source text (used as fallback context)
    quotes: list[SourceQuote]   # chunked, retrievable excerpts
    source_id: str       # unique ID for deduplication
    source_name: str     # human label, e.g. 'CourtListener — USDC SDNY'
    url: str             # canonical source URL for attribution
    published_at: str    # ISO date of the source document
    sensitivity_hints: list[str]   # e.g. ['involves_minor', 'sexual_violence']

class BaseSource(ABC):
    @abstractmethod
    def fetch(self) -> list[CaseItem]:
        """Return up to N candidate cases."""
        pass
```

### CourtListenerSource

```python
# sources/courtlistener.py
# Uses the free CourtListener REST API (https://www.courtlistener.com/api/).
# Endpoint: /api/rest/v3/opinions/?order_by=date_filed%20desc
# Auth: optional API token (rate limits go up with one — get it free).
#
# fetch() strategy:
#   - Pull recent opinions filtered by court tier (default: federal district + appellate)
#   - Skip opinions over N words (the script needs a tight narrative arc, not a treatise)
#   - Skip cases lacking a "facts" section the LLM can ground on
#   - Chunk the opinion into ~200-word excerpts, each becomes a SourceQuote
#   - sensitivity_hints derived from keyword scan on the opinion text
```

### DOJPressSource

```python
# sources/doj_press.py
# Uses the DOJ Office of Public Affairs RSS feed:
#   https://www.justice.gov/news/rss
# These are press releases announcing indictments, sentencings, and major case milestones.
# Well-suited for narrative shorts because they're written for public consumption.
#
# fetch() strategy:
#   - Pull last 30 days of releases
#   - Filter to releases announcing convictions or sentencings (avoid mere indictments
#     where the defendant has not been convicted — defamation risk)
#   - Each release becomes one CaseItem; quotes = paragraphs
```

### ChroniclingAmericaSource

```python
# sources/chronicling_america.py
# Uses the Library of Congress Chronicling America API:
#   https://chroniclingamerica.loc.gov/about/api/
# Searches historical newspapers (1777-1963 indexed; pre-1928 is fully public domain).
# Perfect for "100 years ago today" style historical true crime — zero defamation risk
# because all subjects are long deceased.
#
# fetch() strategy:
#   - Query for crime keywords ("murder", "robbery", "trial", "verdict")
#     restricted to date_min=1850-01-01&date_max=1928-12-31
#   - OCR text from results becomes the body and quotes
#   - Always set sensitivity_hints=['historical'] — gives downstream looser content rules
```

Sources are selected per-run via `config.sources.rotation`. Default rotation: `[courtlistener, doj_press, chronicling_america]` — one per day cycles through.

---

## config.yaml (full schema)

```yaml
# --- Sources ---
sources:
  rotation: [courtlistener, doj_press, chronicling_america]
  courtlistener:
    enabled: true
    api_token: ""              # optional; raises rate limits
    courts: [scotus, ca1, ca2, ca3, ca9, dcd, nysd, cacd]
    max_opinion_words: 8000
    max_candidates_per_run: 10
  doj_press:
    enabled: true
    lookback_days: 30
    only_convictions: true     # skip mere indictments — defamation guardrail
    max_candidates_per_run: 10
  chronicling_america:
    enabled: true
    date_min: 1850-01-01
    date_max: 1928-12-31       # public domain cutoff
    keywords: [murder, robbery, trial, verdict, sentence]
    max_candidates_per_run: 10

# --- Case selection ---
selector:
  min_body_words: 400
  max_body_words: 4000
  skip_sensitivity_hints:      # cases matching any of these are dropped entirely
    - involves_minor
    - sexual_violence_explicit
    - ongoing_investigation
  prefer_recency: 0.3          # weight 0-1; 1.0 = strictly newest first

# --- RAG ---
rag:
  chunk_words: 200
  chunk_overlap_words: 40
  top_k_quotes_for_writer: 8

# --- Writer ---
writer:
  model: gpt-4o-mini
  max_tokens: 1200
  target_words: [600, 750]     # 45-55 seconds spoken
  prompt: |
    You are writing a 45-55 second YouTube Shorts narration for a true-crime channel.
    You will be given source quotes from public records, each tagged with a citation ID.

    Rules — these are non-negotiable:
    1. Every factual claim in the narration MUST be supported by the provided quotes.
       Add inline citations like [doc_p2_para3] after each claim.
    2. Do NOT invent details, motives, names, dates, or quotes that are not in the sources.
    3. Do NOT name any person who has not been convicted in the source material.
       If the sources only describe an indictment, refer to "the defendant" or "the accused."
    4. Do NOT speculate on guilt, motive, or psychology beyond what the sources state.
    5. Open with a hook in the first 3 seconds. Use second-person or vivid scene-setting.
    6. Close with the documented outcome — sentence, verdict, or unresolved status.
    7. Output JSON: {"hook": "...", "body": "...", "outcome": "...", "title_suggestion": "..."}

# --- Verifier ---
verifier:
  model: gpt-4o-mini
  # Verifier extracts each [cite_id]-tagged claim from the script and checks it
  # against the original SourceQuote. Any unsupported claim fails the entire job.
  fail_on_unsupported_claim: true

# --- Safety filter ---
safety:
  model: gpt-4o-mini
  blocklist_terms:             # auto-fail if any appear in script
    - "allegedly killed"       # past-tense unconvicted assertions
    - "is believed to have"
  classifier_categories:       # GPT-4o-mini classifies the script across these
    - defamation_risk          # names + uncharged conduct
    - graphic_violence
    - victim_identifying
    - sexual_content
  max_score_per_category: 2    # 0=clean, 5=severe; >2 fails

# --- TTS ---
tts:
  provider: kokoro             # options: kokoro | elevenlabs
  kokoro:
    voice: am_adam             # serious male voice fits the format
    speed: 1.0
  elevenlabs:
    voice_id: ""
    model: eleven_turbo_v2
    use_alignment_endpoint: true   # skips faster-whisper when true
    monthly_budget_usd: 22         # hard cap; pipeline aborts when reached

# --- Captions ---
captions:
  whisper_model: base          # only used when tts.provider==kokoro
  font: "Noto Sans"
  font_size: 78
  primary_color: "&H00FFFFFF"  # ASS color format (BGR, alpha)
  outline_color: "&H00000000"
  outline_width: 4
  position: middle             # top | middle | bottom
  words_per_flash: 2

# --- Visuals ---
visuals:
  base_layer:
    style: stock_ambient       # slow-moving b-roll under everything else
    pexels_queries:            # rotated per scene
      - "rain night city"
      - "courthouse exterior"
      - "fog forest dark"
      - "old document close up"
    crossfade_seconds: 0.5
  overlays:
    enable_court_docs: true
    enable_newspaper_clippings: true
    enable_animated_map: true
    ken_burns_zoom: 1.15        # subtle zoom on still images
  pexels_api_key_env: PEXELS_API_KEY

# --- Video ---
video:
  output_resolution: [1080, 1920]
  output_fps: 30
  audio_fade_out: 1.5

# --- Upload ---
upload:
  privacy_status_initial: private        # set to private, then publishAt switches it
  schedule_gap_hours: 24                  # 1/day to start
  publish_hour_local: 18                  # 6pm local
  title_template: "{title} #shorts #truecrime"
  description_template: |
    Sourced from public records: {source_name}
    Source URL: {url}

    This video was generated with the assistance of AI tools and contains synthetic
    narration. All facts cited are taken from the linked public record.

    #shorts #truecrime #publicrecords
  category_id: 24                          # Entertainment
  made_for_kids: false
  contains_synthetic_media: true           # AI disclosure flag — required for synthetic voice

# --- Pipeline ---
pipeline:
  max_videos_per_run: 1
  purge_audio_after_render: true
  purge_video_after_upload: true
  purge_scenes_after_render: true
  keep_sources_after_upload: true          # audit trail for legal defense
  dry_run: false

# --- Alerting ---
alerting:
  healthchecks_url: ""                     # https://hc-ping.com/<uuid>
  smtp_on_failure: false
  smtp_to: ""
```

---

## .env file (secrets only)

```
OPENAI_API_KEY=

# Optional alternative TTS
ELEVENLABS_API_KEY=

# Stock footage
PEXELS_API_KEY=

# Optional, raises CourtListener rate limits
COURTLISTENER_API_TOKEN=

# YouTube OAuth client (from Google Cloud Console)
YOUTUBE_OAUTH_CLIENT_ID=
YOUTUBE_OAUTH_CLIENT_SECRET=
# Refresh token lives in token.json after one-time OAuth flow

# Optional alerting
HEALTHCHECKS_URL=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
```

---

## Pipeline step specifications

### Step 1 — Orchestrator (`main.py`)

```
1. Load config.yaml and .env
2. Initialise logger (rotating file + stdout)
3. Initialise SQLite database (create tables if not exist)
4. Pick today's source from config.sources.rotation
5. Instantiate that source adapter, call fetch() → list[CaseItem]
6. selector.choose(candidates) → filter by used_ids, length, sensitivity → ranked list
7. For up to config.pipeline.max_videos_per_run cases:
     a. Mark job PENDING in db, store source_id + source_name + url
     b. rag.build_context(case) → top-k quotes
     c. writer.write(case, quotes) → {hook, body, outcome, title}
     d. verifier.check(script, quotes) → on unsupported claim: mark FAILED, alert, next
     e. safety.scan(script) → on block: mark SAFETY_BLOCKED, next
     f. tts.synthesize(script) → audio path
     g. captions.build(audio, script) → ASS subtitle path
     h. scene_planner.plan(script, captions) → list of (start, end, scene_spec)
     i. assets.render_scenes(plan) → list of scene PNG/MP4 paths
     j. composer.render(audio, captions, scenes) → final mp4 path
     k. Mark job UPLOADING (idempotent guard against re-upload)
     l. uploader.upload(mp4, metadata) → video_id, scheduled_for
     m. Mark job COMPLETE, store video_id and scheduled_for
     n. Purge intermediate files per config flags
     o. On any exception: mark FAILED, log full traceback, alert.notify_failure(), continue
8. Log summary: N completed, N failed, N safety-blocked
```

Cron entry (uses droplet local TZ set in setup step 2):

```
0 10 * * * /root/true-crime-shorts-bot/venv/bin/python /root/true-crime-shorts-bot/main.py >> /root/true-crime-shorts-bot/logs/cron.log 2>&1
```

### Step 2 — RAG (`pipeline/rag.py`)

- Chunk `case.body` into ~200-word windows with 40-word overlap if `case.quotes` is empty
- For seeded `case.quotes`, use as-is
- For writer: select top-k quotes via simple BM25 over a generic crime-narrative query bank ("what happened, who was charged, what was the outcome, when did it occur, where, what evidence")
- Return list[SourceQuote] passed verbatim into the writer prompt

No vector DB. At <50 quotes per case BM25 is faster and simpler.

### Step 3 — Writer (`pipeline/writer.py`)

- Build user message containing:
  - Case title and source name
  - Numbered list of SourceQuote excerpts with their `cite_id`s
  - Instructions matching `config.writer.prompt`
- Call GPT-4o-mini with `response_format={"type": "json_object"}`
- Parse JSON; warn-and-fail if structure invalid
- Concatenate `hook + " " + body + " " + outcome` as the final narration string
- Strip citations from the spoken version (keep them only in the structured output for the verifier)
- Validate word count is within `config.writer.target_words`
- Return `{script_spoken, script_with_citations, title}`

### Step 4 — Verifier (`pipeline/verifier.py`)

- Parse all `[cite_id]` tags out of `script_with_citations` → list of (claim_sentence, cite_id) pairs
- For each pair, call GPT-4o-mini with: "Does the following quote support this claim? Answer YES or NO with one-sentence reason."
  - Quote = SourceQuote.text for that cite_id
  - Claim = the sentence containing the citation
- Any NO with `fail_on_unsupported_claim: true` → raise `VerificationFailed`
- Log all verifications for audit

This is the single most important safety mechanism. Without it the pipeline is one hallucination away from the True Crime Case Files outcome.

### Step 5 — Safety filter (`pipeline/safety.py`)

- Hard-fail on any `blocklist_terms` substring match
- Call GPT-4o-mini with the script and a rubric:
  - Score 0-5 on each `classifier_categories` key
  - Return JSON `{defamation_risk: N, graphic_violence: N, ...}`
- Any category exceeding `max_score_per_category` → raise `SafetyBlocked`
- Log every score for tuning

### Step 6 — TTS (`pipeline/tts.py`)

- `config.tts.provider == "kokoro"`: load model once (module-level cache), call `generate(voice, speed)`, save as .mp3
- `config.tts.provider == "elevenlabs"`:
  - Check daily usage against `monthly_budget_usd` (track in db) — abort if cap reached
  - POST to `/v1/text-to-speech/{voice_id}` with `eleven_turbo_v2`
  - If `use_alignment_endpoint: true`, also POST to `/v1/text-to-speech/{voice_id}/with-timestamps` and persist the timestamps for the captions step
- Return path to .mp3 (+ optional timestamps blob)

### Step 7 — Captions (`pipeline/captions.py`)

Two paths depending on TTS provider:

**Kokoro path:**
- Load faster-whisper model (cached after first load)
- Transcribe with `word_timestamps=True`
- Build word list: `[{word, start_s, end_s}, ...]`

**ElevenLabs path:**
- Use the alignment data returned by TTS — skip whisper entirely

Either way, write an **ASS subtitle file** chunked by `words_per_flash`. ASS format supports per-style font, color, outline, position, animation. Burning ASS via FFmpeg's `subtitles` filter is one command and uses libass — far cheaper than per-word TextClips.

Example ASS event (one chunk):
```
Dialogue: 0,0:00:02.13,0:00:02.71,Default,,0,0,0,,{\an5\pos(540,960)}IT BEGAN
```

### Step 8 — Scene planner (`pipeline/scene_planner.py`)

Given the script and word timestamps, produce a list of timed scene specs:

```python
[
  {"start": 0.0, "end": 3.0,  "type": "stock", "query": "rain night city"},
  {"start": 3.0, "end": 8.5,  "type": "court_doc", "doc_text": "..."},
  {"start": 8.5, "end": 14.0, "type": "newspaper", "clipping_url": "..."},
  {"start": 14.0,"end": 20.0, "type": "map", "lat": 40.7, "lng": -74.0, "label": "Manhattan, 1923"},
  {"start": 20.0,"end": 55.0, "type": "stock", "query": "courthouse exterior"},
]
```

Strategy:
- Hook (first 3s): always stock with strong motion
- Each citation paragraph in the script gets a related visual: a court doc render if the source was CourtListener, a newspaper clipping if Chronicling America, a press release crop if DOJ
- Location mentions in the script trigger an animated map
- Outcome (last 5s): courthouse exterior or gavel close-up

### Step 9 — Assets (`pipeline/assets.py`)

Each scene type has a renderer that produces a 1080×1920 PNG (or short MP4 for stock clips):

- `stock`: search Pexels API for the query, pick a clip that's already cached locally, or download + cache. Center-crop to 9:16. Slow Ken Burns zoom applied at composition time.
- `court_doc`: render an HTML template (`assets/templates/court_doc.html`) populated with the doc text and case caption → headless Chrome screenshot → save PNG.
- `newspaper`: fetch the page image from Chronicling America (already in `case.url`), crop to the relevant column, apply sepia + paper-grain CSS filter via HTML template.
- `map`: render a Mapbox Static Image (free tier 50k/month) at the given coords, overlay a marker + label.

Cache aggressively: every Pexels query result is keyed by query string + clip ID; rendered docs and maps are keyed by content hash. The droplet should warm up quickly.

### Step 10 — Composer (`pipeline/composer.py`)

Single FFmpeg pass:

```
ffmpeg \
  -i base_concat.mp4 \           # the scene timeline pre-concatenated with crossfades
  -i narration.mp3 \             # TTS audio
  -vf "subtitles=captions.ass" \ # burn ASS subtitles via libass
  -map 0:v -map 1:a \
  -c:v libx264 -preset fast -crf 22 \
  -c:a aac -b:a 128k \
  -shortest \
  -y output/videos/{job_id}.mp4
```

Building `base_concat.mp4`: use FFmpeg's `concat` demuxer to splice the scene PNGs/clips with crossfades. Each still image scene gets a Ken Burns motion via FFmpeg's `zoompan` filter (preserves the "alive" feel without an editor).

This is one process, one memory footprint. The earlier MoviePy + 75 TextClips design would have peaked at >1.5GB; this peaks under 400MB.

### Step 11 — Uploader (`pipeline/uploader.py`)

Uses `google-api-python-client` with OAuth refresh token from `token.json`.

```
1. Refresh the access token using the stored refresh token
2. Determine the next publish slot: query db for latest scheduled_for,
   add config.upload.schedule_gap_hours, snap to config.upload.publish_hour_local
3. Build the metadata body:
     snippet.title, snippet.description, snippet.categoryId, snippet.tags
     status.privacyStatus = "private"
     status.publishAt = next_publish_slot.isoformat()  # this triggers scheduling
     status.selfDeclaredMadeForKids = false
     status.containsSyntheticMedia = true  # the AI disclosure flag
4. Resumable upload of the mp4 via videos().insert(part="snippet,status")
5. Capture video_id from response
6. Mark job COMPLETE in db with video_id + scheduled_for
7. Return video_id
```

**Quota math:** YouTube Data API gives 10,000 units/day default. An upload costs 1,600 units. So you can upload up to 6 videos per day on the default quota — well above the 1-2/day target. No quota increase needed unless you scale much higher.

**Idempotency:** the orchestrator marks the job `UPLOADING` *before* calling `insert()`. If the script crashes mid-upload and reruns, the next run sees `UPLOADING`, queries YouTube `videos.list?forMine=true` for matching title fingerprint, and either marks COMPLETE (already uploaded) or retries upload. No double-uploads.

**Retry policy:** wrap the resumable upload in retry-with-exponential-backoff for `5xx` and network errors. Do not retry on `4xx` (those are config or content problems — fix them, don't hammer).

### Step 12 — Alerting (`pipeline/alert.py`)

- On `notify_failure(job_id, exception)`:
  - If `HEALTHCHECKS_URL` set: POST a failure ping to `{HEALTHCHECKS_URL}/fail` with the traceback
  - If `smtp_on_failure` true: send a short email to `smtp_to`
- On `notify_success(...)` at end of run: ping `{HEALTHCHECKS_URL}` (no `/fail`)

Healthchecks.io is free for one check, gives you alerting on missed runs + on failures with zero infra.

---

## SQLite schema (`db/database.py`)

```sql
CREATE TABLE IF NOT EXISTS used_sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    source_name TEXT,
    source_url TEXT,
    title TEXT,
    script TEXT,
    citations_json TEXT,
    status TEXT DEFAULT 'PENDING',
        -- PENDING | IN_PROGRESS | UPLOADING | COMPLETE | FAILED | SAFETY_BLOCKED
    video_id TEXT,
    scheduled_for TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS upload_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    scheduled_for TIMESTAMP UNIQUE,
    video_id TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS elevenlabs_usage (
    month TEXT PRIMARY KEY,           -- 'YYYY-MM'
    chars_billed INTEGER DEFAULT 0,
    usd_estimated REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS safety_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    category TEXT,
    score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
```

---

## requirements.txt

```
openai>=1.40.0
elevenlabs>=1.0.0
kokoro-onnx>=0.3.0
faster-whisper>=1.0.0
google-api-python-client>=2.130.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
requests>=2.31.0
feedparser>=6.0.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
pyyaml>=6.0
python-dotenv>=1.0.0
rank-bm25>=0.2.2
pillow>=10.0.0
```

(MoviePy and PRAW are intentionally omitted. Playwright is kept only for HTML→PNG rendering of court doc and newspaper templates, not for YouTube upload.)

---

## README sections to include

1. **Prerequisites** — Python 3.10+, FFmpeg with libass system-wide, Noto Sans font, Google Cloud project with YouTube Data API v3 enabled
2. **Hosting** — DigitalOcean Basic Droplet (2GB RAM, Ubuntu 24.04, $12/mo); $200 free credit link
3. **Installation** — full server setup commands (timezone, apt deps incl. libass9, venv, pip install, playwright install chromium)
4. **API key setup** — OpenAI, Pexels (free), ElevenLabs (optional), CourtListener (optional)
5. **YouTube OAuth setup** — create OAuth client in Google Cloud Console, run `scripts/youtube_oauth.py` locally, scp `token.json` to droplet; document refresh-token longevity (Google refresh tokens are long-lived but can be invalidated — pipeline alerts on auth failure)
6. **AI synthetic content disclosure** — `containsSyntheticMedia: true` is set automatically on every upload; this is required by YouTube for AI-generated narration; failing to disclose can result in channel suspension
7. **Stock asset seeding** — `python scripts/seed_stock_assets.py` warms the cache
8. **First run** — `python main.py --dry-run` to test without uploading
9. **Cron setup** — exact crontab entry; reminder to set timezone first
10. **Monitoring** — log grep commands; setting up a Healthchecks.io ping URL
11. **Adding new sources** — one paragraph explaining BaseSource + the SourceQuote contract
12. **Editorial guardrails** — explain the verifier + safety filter philosophy; under what conditions to tune `safety.max_score_per_category` thresholds
13. **Legal posture** — public-record sourcing only, no naming uncharged suspects, no AI faces of real people, audit trail kept in `output/sources/`
14. **Troubleshooting** — common issues: OAuth refresh token revoked, Pexels rate limit, faster-whisper model download on first run, FFmpeg libass missing

---

## Error handling requirements

- Every pipeline step wrapped in try/except at the orchestrator level
- On step failure: log full traceback (incl. job_id and source_id), mark job FAILED, call `alert.notify_failure`, continue to next job
- On `VerificationFailed`: same as FAILED, but also log the unsupported claims for review
- On `SafetyBlocked`: mark SAFETY_BLOCKED (distinct from FAILED), log the category scores, do not alert (not a system problem)
- On upload auth failure: log clear warning — "YouTube OAuth token may have been revoked. Re-run scripts/youtube_oauth.py" — do not retry upload, do not delete the rendered video, alert
- On ElevenLabs budget exceeded: log warning, skip the job, alert
- On 3+ consecutive FAILEDs across runs: alert with "pipeline is stuck" message

---

## Dry run mode

`python main.py --dry-run`

- All steps run through composition
- Upload step skipped
- Rendered video kept in `output/videos/` for manual inspection
- Script + citation map kept in `output/scripts/`
- Log clearly states "DRY RUN — skipping upload"

---

## First-milestone checklist (build order)

The original spec said "Reddit fetch → LLM rewrite → TTS → print transcript first." Adapt that to true crime — get the editorial pipeline working before touching video. Recommended build order:

1. **Sources + selector + RAG**: pull a real case from CourtListener, chunk it, BM25-rank quotes. Print to console.
2. **Writer + verifier + safety**: generate a script with citations, run verification, run safety. Print the script and the verification log. Iterate the writer prompt until verifier passes consistently.
3. **TTS + captions**: synthesize the script, build the ASS file, play locally.
4. **Scene planner + assets**: render one of each scene type to PNG/MP4 standalone.
5. **Composer**: render the full video with one source case end-to-end. Watch it.
6. **Uploader**: OAuth flow, upload one video as `private` (no `publishAt`), confirm it appears in Studio.
7. **Orchestrator + cron + alerting**: wire everything, run dry-run on droplet, then enable scheduled publish, then cron.

Build and test each module in isolation before wiring. Use `pytest tests/` with at least one test per module using fixtures (a cached CourtListener response, a sample script with known citations, etc.).

---

## Future extension notes

Include as comments in the codebase:

- `sources/`: add NewsAPI for recent coverage; add NamUs RSS for missing-persons cases (very high engagement, requires extra sensitivity tuning); add state court portals (varies wildly)
- `pipeline/writer.py`: A/B test prompt variants; track which variants survive verification at a higher rate
- `pipeline/assets.py`: add AI-generated abstract scenes via a strict "no real people, no recognizable faces" prompt (Runway/Veo when budget allows)
- `pipeline/uploader.py`: add TikTok as a second destination — same video, same schedule
- A retention tracker: pull YouTube Analytics API data and feed retention curves back into the scene planner (which hooks survived, which lost viewers)
- A long-form back end: stitch 60-minute compilations of past Shorts for the channel's main feed — different RPM economics, same source pipeline
