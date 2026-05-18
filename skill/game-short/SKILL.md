---
name: game-short
description: Produce a 40-50 second YouTube Short about an upcoming or recently released video game. Fetches the official trailer from Steam (or YouTube as fallback), selects 4 portrait-cropped clip segments, writes a 4-beat narration script, generates ElevenLabs TTS audio, and renders a portrait video with trailer clips as background and ASS captions. Use when Justin asks to make a game short, cover a specific game, or run the next item from game_queue/.
version: 1.0.0
---

# game-short

End-to-end pipeline that turns a game's trailer into a narrated YouTube Short.
Background visuals are real trailer clips (not static PNGs). Targets the gaming
algorithm via category "20" (Gaming) and gaming-specific tags.

## When to invoke

- "Make a short about [game name]"
- "Cover the new [game] trailer"
- "Run the next game from the queue"
- Any request to produce a vertical video short about a video game

## Required inputs

Either:
- A `game_queue/GG_NN_<slug>.md` file (use the GG_TEMPLATE.md as a starting point), OR
- A game title + one of: Steam App ID or YouTube trailer URL

## Hard rules

1. **Trailer clips only** — no AI-generated imagery, no third-party screenshots.
2. **No developer/studio interview footage** — clip selection must use gameplay or CGI trailer segments only, not talking heads.
3. **AI synthetic content disclosure** on every upload (same as truecrime pipeline).
4. **No fabricated release dates, prices, or platform availability.** If uncertain, omit.
5. **No hyperbole** ("mind-blowing", "best game ever") — concrete mechanics over abstract praise.

## Phase flow

### Phase 0 — Game selection
Present next QUEUED item from `game_queue/_INDEX.md` or use provided game/ID.

### Phase 1 — Fetch trailer
```bash
python scripts/fetch_trailer.py --steam <appid> --game-id <game_id>
# or:
python scripts/fetch_trailer.py --youtube <url> --game-id <game_id>
```
Output: `output/scripts/<game_id>/trailer_raw.mp4`

### Phase 2 — Select clips
```bash
# Auto mode (no manual input needed):
python scripts/select_clips.py --game-id <game_id> --auto

# Manual mode (Justin specifies timestamps after watching trailer):
python scripts/select_clips.py --game-id <game_id> \
  --clips '[{"start":10,"end":22,"label":"hook"},{"start":35,"end":47,"label":"gameplay"},{"start":60,"end":72,"label":"standout"},{"start":85,"end":95,"label":"cta"}]'
```
Output: `output/scripts/<game_id>/clips/clip_01.mp4` … `clip_04.mp4` + `clips_manifest.json`

Show the `clips_manifest.json` to Justin. Allow clip substitution before proceeding.

### Phase 3 — Script
Apply `skill/game-short/writer_prompt.md` over the game_queue entry's 4-beat arc.
Present the script. **Wait for approval before generating audio.**

### Phase 4 — TTS
```bash
python scripts/make_audio_elevenlabs.py --case <game_id>
```
Output: `assets/audio/narration_<game_id>.mp3`

### Phase 5 — Render
Write `output/scripts/<game_id>/game_config.json` from the approved script + clips manifest.
```bash
python skill/game-short/render_game_video.py output/scripts/<game_id>/game_config.json
```
Then FFmpeg encode:
```bash
ffmpeg -y -f concat -safe 0 \
    -i output/scripts/<game_id>/bg_clips_concat.txt \
    -i assets/audio/narration_<game_id>.mp3 \
    -vf "subtitles=output/scripts/<game_id>/captions.ass" \
    -map 0:v -map 1:a \
    -c:v libx264 -preset fast -crf 22 \
    -c:a aac -b:a 128k -shortest -movflags +faststart \
    output/game_videos/<game_id>.mp4
```

### Phase 6 — Delivery
- Write `output/game_videos/<game_id>.mp4`
- Write `output/game_videos/<game_id>.description.md` (use `skill/game-short/description_template.md`)
- Update `game_queue/_INDEX.md` status: QUEUED → DELIVERED
- Upload: `python scripts/upload_to_youtube.py --case <game_id> --videos-dir output/game_videos --category 20`

## game_config.json schema

```json
{
  "game_id": "GG_01_elden_ring_dlc",
  "audio_file": "assets/audio/narration_GG_01_elden_ring_dlc.mp3",
  "clips_manifest": "output/scripts/GG_01_elden_ring_dlc/clips_manifest.json",
  "game_title": "ELDEN RING: SHADOW OF THE ERDTREE",
  "platform": "PC / PS5 / XBOX",
  "release_label": "OUT NOW",
  "beats": [
    {"label": "hook", "text": "..."},
    {"label": "gameplay", "text": "..."},
    {"label": "standout", "text": "..."},
    {"label": "cta", "text": "..."}
  ]
}
```

## Per-game output structure

```
output/scripts/<game_id>/
  ├── trailer_raw.mp4           # downloaded trailer
  ├── clips/
  │   ├── clip_01.mp4           # hook segment
  │   ├── clip_02.mp4           # gameplay segment
  │   ├── clip_03.mp4           # standout segment
  │   └── clip_04.mp4           # CTA segment
  ├── clips_manifest.json
  ├── clips_portrait/           # portrait-cropped + overlay applied
  ├── bg_clips_concat.txt       # ffmpeg concat list for portrait clips
  ├── captions.ass              # ASS subtitle file
  └── game_config.json

output/game_videos/
  ├── <game_id>.mp4
  ├── <game_id>.description.md
  └── _posted_games.json        # upload tracking (mirrors _posted.json)
```
