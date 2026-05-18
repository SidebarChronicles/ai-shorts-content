"""Atomic file write helpers.

Use these for any state file whose corruption would break the pipeline —
_posted.json, elevenlabs_usage.json, token.json, game_queue/*.md.

Why atomic: path.write_text() truncates then writes. A crash, SIGKILL, or
full disk between truncate and write leaves the file empty. Empty
_posted.json → daily cron re-uploads every video. Empty token.json →
channel locked out until manual re-auth.

os.replace() is atomic on POSIX when source and dest share a filesystem,
so we write the temp file in the same directory as the destination.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, data: str) -> None:
    """Write text to path atomically via tempfile + os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of orphan tmp on failure
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, obj, indent: int = 2, sort_keys: bool = True) -> None:
    """Write a JSON object to path atomically."""
    atomic_write_text(path, json.dumps(obj, indent=indent, sort_keys=sort_keys) + "\n")
