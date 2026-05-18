---
description: List all TrueCrime Shorts in the queue with their posted/ready status. Quick way to check what's left to publish.
---

You are running inside Claude Code on Justin's Mac.

Run the uploader's list mode and report the output verbatim:

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/upload_to_youtube.py --list
```

This shows every case with an mp4 + description sidecar, marked `[POSTED]` (with watch URL) or `[READY]`. The posted state lives in `output/videos/_posted.json`.
