---
description: Upload the next unposted YouTube Short via the Data API v3 — scheduled as private→public at the next 6 PM local time at least 24h out, with AI synthetic-content disclosure set.
---

You are running inside Claude Code on Justin's Mac. You have full shell + file access.

Run the uploader script for the next case that hasn't been posted yet:

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/upload_to_youtube.py --next
```

Then report back:
- Which case_id was uploaded
- The video_id YouTube returned
- The scheduled publish time
- The watch URL (https://www.youtube.com/watch?v={id})

**If the script fails:**
- `No token.json` → tell Justin to run `python scripts/youtube_oauth_setup.py` first
- `Missing client_secret.json` → tell Justin to do the Google Cloud setup (see README_UPLOAD_SETUP.md)
- `All cases have been posted` → tell Justin the queue is empty; he can produce more or invoke `/upload-case <id>` to repost
- Auth error / 401 / 403 → tell Justin the OAuth token may have been revoked; rerun `youtube_oauth_setup.py`
- 5xx errors → script auto-retries; if it still fails, show the full traceback

**If it succeeds:**
- Confirm the AI synthetic-content disclosure was set (the script always sets it; just remind Justin it's in)
- Remind Justin he can view it in YouTube Studio under "Content" → it'll show as Scheduled until the publish time
- Suggest the obvious next step: queue another case, or check retention on the previous video
