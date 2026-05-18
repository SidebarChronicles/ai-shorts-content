---
description: Produce a 40-50 second YouTube Short about a video game. Fetches the trailer from Steam (or YouTube), selects 4 portrait-cropped clips, writes a 4-beat script, generates ElevenLabs TTS audio, renders a clip-background video with captions, and outputs a finished mp4 + description sidecar.
argument-hint: optional game title, Steam App ID, or GG queue ID
---
You are running inside Claude Code on Justin's Mac.

Produce a game short using the skill/game-short/ pipeline. Follow these steps exactly:

**Step 0 — Select game**
If $ARGUMENTS is provided, find the matching game_queue/GG_*.md file or treat it as a game title to look up.
If no argument, read game_queue/_INDEX.md and pick the next QUEUED entry.
Show Justin: game title, Steam App ID, release date, and hook.

**Step 1 — Fetch trailer**
```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/fetch_trailer.py --steam <appid> --game-id <game_id>
# or if no Steam ID:
python scripts/fetch_trailer.py --youtube <url> --game-id <game_id>
```
Report: file size, duration.

**Step 2 — Auto-select clips**
```bash
python scripts/select_clips.py --game-id <game_id> --auto
```
Show Justin the clips_manifest.json. Ask: "Do these timestamps look good, or do you want to provide manual timestamps?"
Allow clip substitution before proceeding.

**Step 3 — Generate script**
Apply skill/game-short/writer_prompt.md over the game_queue entry's 4-beat arc.
Present the 3 title options and the full script_spoken. 
**Wait for explicit approval before generating audio.**

**Step 4 — TTS**
```bash
python scripts/make_audio_elevenlabs.py --case <game_id>
```
Report: audio duration, cost.

**Step 5 — Write game_config.json**
Write output/scripts/<game_id>/game_config.json with the approved script beats + clips manifest + game metadata.

**Step 6 — Render**
```bash
python skill/game-short/render_game_video.py output/scripts/<game_id>/game_config.json
```
Then run the FFmpeg command that the script prints.

**Step 7 — Deliver**
- Confirm output/game_videos/<game_id>.mp4 exists and has a reasonable duration (40–50s)
- Write output/game_videos/<game_id>.description.md (use skill/game-short/description_template.md)
- Update game_queue/_INDEX.md: QUEUED → DELIVERED

**Report back:**
- Game title and game_id
- Audio duration
- Output mp4 path
- To upload: `python scripts/upload_to_youtube.py --case <game_id> --videos-dir output/game_videos --category 20`

**If fetch_trailer.py fails:**
- Steam `appdetails` returns no trailer → try `--youtube <official trailer URL>`
- yt-dlp not installed → `pip install yt-dlp`
- Download error → show the full error message

**If make_audio_elevenlabs.py fails:**
- No API key → tell Justin to set ELEVENLABS_API_KEY in .env
- Budget exceeded → show current month usage from output/elevenlabs_usage.json
