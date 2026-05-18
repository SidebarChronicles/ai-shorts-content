"""Hardened .env loader.

Replaces ad-hoc loaders that mishandle quotes, inline comments, and
precedence. Call once at script startup.

Semantics:
- Lines starting with '#' are comments (skipped).
- Blank lines skipped.
- KEY=VALUE format (first '=' splits).
- Surrounding matching " or ' quotes are stripped from VALUE.
- Unquoted ' #' (space-hash) is treated as the start of an inline
  comment; everything after is dropped.
- Existing os.environ keys win (setdefault semantics) so cron-exported
  vars override .env.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | str | None = None) -> int:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Returns the number of keys set. Missing file → returns 0 silently.
    """
    if path is None:
        # Default: <project_root>/.env (caller passes explicit path otherwise)
        path = Path(__file__).resolve().parent.parent / ".env"
    path = Path(path)
    if not path.exists():
        return 0

    n_set = 0
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Strip inline comment (only if unquoted)
        if not (value.startswith('"') or value.startswith("'")):
            # Look for " #" or trailing # comment
            hash_idx = value.find(" #")
            if hash_idx >= 0:
                value = value[:hash_idx].rstrip()

        # Strip matching surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        if key and key not in os.environ:
            os.environ[key] = value
            n_set += 1

    return n_set
