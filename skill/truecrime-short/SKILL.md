---
name: truecrime-short
description: Produce a fact-grounded 45-55 second YouTube Short from a public-record true-crime case. Pulls source documents, writes a verified narration with inline citations, runs a defamation/graphic-content safety filter, renders stylized scene visuals with word-level captions, and outputs a finished mp4 plus YouTube description and metadata sidecar. Use when the user asks to produce a true-crime short, queue a new case, or run the next item in case_queue/.
version: 1.0.0
---

# truecrime-short

End-to-end pipeline that turns a DOJ press release (or similar public court record) into a finished YouTube Short. Built and validated on the GothFerrari run (output/scripts/01_gothferrari/).

## When to invoke

- "Make me a true-crime short on [topic]"
- "Run the next case from the queue"
- "Produce video for case #N"
- "Build the GothFerrari-style video for X"
- Any request that combines a public court record with short-form vertical video output

## Required inputs

Either:
- An existing case file in `case_queue/<NN>_<slug>.md` with body text + source URL, OR
- A fresh DOJ/court URL (skill will run Phase 0 research first)

## Hard rules

These are non-negotiable. Encoded in `writer_prompt.md` and `safety_rules.md`:

1. **Every claim in the narration must map to a SourceQuote.** No invented details, dates, names, dollar amounts. Verified by a second-pass classifier.
2. **No naming of uncharged people.** Use "the defendant" if the source only describes an indictment.
3. **No AI-generated faces of real people.** Visual layer uses generated typography + abstract shapes only.
4. **No external links in descriptions** (channel restriction — see `description_template.md`).
5. **AI synthetic content disclosure** is set on every video (YouTube May 2025 policy).

## Phase flow

1. **Phase 0 — Research** (skip if case_queue file exists)
   - Search DOJ press releases for conviction announcements
   - Score candidates on narrative arc, visual material, sensitivity
   - Save 6-8 to case_queue/

2. **Phase 1 — Selection**
   - Present queue to user, await pick (or take provided case number)

3. **Phase 2 — RAG**
   - Load case_queue/<NN>_*.md
   - Chunk the press release into 8-12 cite-tagged quotes
   - Save to `output/scripts/<case_id>/sources.json`

4. **Phase 3 — Script**
   - Apply `writer_prompt.md` over the quotes
   - Output script + claims_index
   - Run verifier: every claim must cite a quote
   - Run safety classifier (defamation, graphic, victim-identifying, sexual)
   - Save `output/scripts/<case_id>/script.md`

5. **Phase 4 — User approval**
   - Present script in chat
   - Wait for "approved" / edit requests

6. **Phase 5 — Assembly**
   - Generate TTS audio via ElevenLabs:
     ```bash
     python scripts/make_audio_elevenlabs.py --case NN
     ```
     Output: `assets/audio/narration_NN.mp3` + `.alignment.json`
     Fallback (no API key): `bash scripts/make_audio.sh` (macOS `say` only)
   - Render scenes via `render_video.py` driven by case_config.json
   - Bake captions into per-chunk PNG frames
   - FFmpeg concat + audio mux → mp4:
     ```bash
     ffmpeg -y -f concat -safe 0 -i timeline_baked.txt \
         -i assets/audio/narration_NN.mp3 \
         -vf "scale=720:1280,format=yuv420p" \
         -c:v libx264 -preset ultrafast -crf 28 -g 60 \
         -c:a aac -b:a 96k -shortest -movflags +faststart \
         output/videos/<case_id>.mp4
     ```

7. **Phase 6 — Delivery**
   - Write `output/videos/<case_id>.mp4`
   - Write `output/videos/<case_id>.description.md` (no external links)
   - Write `output/videos/<case_id>.metadata.txt`
   - Update `case_queue/_INDEX.md` status: ACTIVE → USED

## Bundled assets

- `writer_prompt.md` — proven 6-beat writer template with citation rules
- `safety_rules.md` — defamation + graphic + victim-identifying classifier
- `description_template.md` — YouTube description template, NO external links
- `visual_style_guide.md` — color palette, typography, scene template patterns
- `case_config_schema.md` — JSON shape that drives the renderer per case
- `render_video.py` — generalized scene + caption + concat renderer

## Per-case files produced

```
output/scripts/<case_id>/
  ├── sources.json              # cite-tagged quotes (RAG)
  ├── script.md                 # narration + verifier + safety logs
  ├── case_config.json          # scene plan (drives renderer)
  ├── scenes/                   # rendered scene PNGs
  └── frames/                   # caption-baked frames

output/videos/
  ├── <case_id>.mp4
  ├── <case_id>.description.md
  └── <case_id>.metadata.txt
```

## Environment notes

- TTS is ElevenLabs (`scripts/make_audio_elevenlabs.py`) — requires `ELEVENLABS_API_KEY` in env. See `.env.example`.
- Legacy fallback: `make_audio.sh` uses macOS `say` (Daniel voice, AIFF) — only if no API key is set.
- 45s bash timeout per command — encode at 720x1280 with `-preset ultrafast -tune stillimage`, skip libass at runtime by pre-baking captions into PNGs
- All scene assets generated programmatically (PIL) — no external stock library required

## Reference run

`output/scripts/01_gothferrari/` — verified script + finished mp4. Reproduce its style/quality for each new case.
