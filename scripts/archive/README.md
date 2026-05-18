# scripts/archive — obsolete narration tooling

Scripts kept for historical context only. **Do not run.** They predate the ElevenLabs TTS migration.

| File | What it did | Replaced by |
|---|---|---|
| `make_audio.sh` | Generated narration via macOS `say` (one case) | `scripts/make_audio_elevenlabs.py --case <id>` |
| `make_audio_batch.sh` | Same, batch across cases 02-06 | `scripts/make_audio_elevenlabs.py --case <id>` |

The macOS `say` voice was inadequate (robotic, no alignment data for karaoke captions). ElevenLabs is the production standard.
