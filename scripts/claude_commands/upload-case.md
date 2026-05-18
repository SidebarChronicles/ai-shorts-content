---
description: Upload a specific TrueCrime Short by case number (e.g. `/upload-case 02` for the ransomware negotiator). Same auth + scheduling + AI disclosure as /upload-next-video.
argument-hint: <case_id, e.g. 02 or 03_fugitive_crypto_scam>
---

You are running inside Claude Code on Justin's Mac. You have full shell + file access.

Justin has invoked `/upload-case` with the argument: $ARGUMENTS

Run the uploader script for that specific case:

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/upload_to_youtube.py --case "$ARGUMENTS"
```

If `$ARGUMENTS` is empty or doesn't match a known case, list the available cases first:

```bash
python scripts/upload_to_youtube.py --list
```

Then ask Justin which case_id he meant.

Report the same fields as /upload-next-video: case_id uploaded, video_id, scheduled publish time, watch URL. Apply the same error-handling rules.
