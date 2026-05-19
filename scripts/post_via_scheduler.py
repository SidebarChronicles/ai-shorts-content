#!/usr/bin/env python3
"""Autonomous cross-poster: queue rendered videos to PostFast (TikTok + IG Reels).

PostFast (https://postfa.st) fronts the TikTok Content Posting API + Meta
Graph API via their pre-approved developer apps, so we don't have to file
our own app reviews (2-6 week wait). We push each rendered MP4 + its caption
sidecar to PostFast's API; PostFast handles platform OAuth, transcoding,
and publish.

Why this script exists (v2 strategy, May 18 2026):
    Manual cross-post at 8 videos/day = ~24 min/day = ~12 hrs/mo.
    TT + IG are the lottery-driven volume drivers; YouTube is the gated tail.
    Autonomous TT + IG is higher leverage than autonomous YT (already exists).

PostFast API flow (per video, per platform):
    1. POST /file/get-signed-upload-urls    → {signedUrl, key} for S3 upload
    2. PUT  <signedUrl>  with raw MP4 bytes → 200
    3. POST /social-posts                   → {posts: [{...mediaItems[{key,...}]...}]}
       PostFast then forwards to TikTok / IG with the platform-mandated
       AI-content flag (configured per-account in PostFast dashboard).

Usage:
    # Routine STEP 4 default — queue every pending case to both platforms
    python3 scripts/post_via_scheduler.py --all-pending

    # Single case
    python3 scripts/post_via_scheduler.py --case SY_05_H_basement

    # Single case, one platform only (TT only while IG is being set up)
    python3 scripts/post_via_scheduler.py --case SY_05_H_basement --platforms tt

    # Dry-run (no API calls; print what would happen)
    python3 scripts/post_via_scheduler.py --all-pending --dry-run

    # Probe API key + list connected accounts (surfaces social_media_id values)
    python3 scripts/post_via_scheduler.py --check-auth

Required env vars (in .env):
    POSTFAST_API_KEY                Workspace API key from PostFast dashboard
    POSTFAST_TIKTOK_CHANNEL_ID      social_media_id (UUID) of the TT account
    POSTFAST_INSTAGRAM_CHANNEL_ID   social_media_id (UUID) of the IG account
    POSTFAST_BASE_URL               (optional) override; default https://api.postfa.st

Idempotency:
    On 2xx success we mark <case>.tiktok / .instagram in cross_post_status.json
    atomically. On any non-2xx we leave the tracker untouched, so the next
    invocation retries that (case, platform) pair while skipping ones that
    already posted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib import error as urlerror
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _atomic import atomic_write_json  # noqa: E402
from _env import load_dotenv  # noqa: E402

# Import the existing tracker helpers so we share the data model (no schema drift)
from cross_post_status import (  # noqa: E402
    SKIPPED_MARKER,
    load_status,
    refresh_from_posted_ledgers,
    save_status,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.postfa.st"
THROTTLE_SECONDS = 5.0      # gap between successful post creations
REQUEST_TIMEOUT = 180       # seconds — S3 PUTs can take a moment for ~5MB MP4

PLATFORM_TT = "tiktok"
PLATFORM_IG = "instagram"
ALL_PLATFORMS = (PLATFORM_TT, PLATFORM_IG)

# Map the short-form CLI value (tt|ig|both) to platform keys
PLATFORM_CLI_MAP = {
    "tt": (PLATFORM_TT,),
    "ig": (PLATFORM_IG,),
    "both": ALL_PLATFORMS,
}

# PostFast's platform-name conventions (the labels they return on the auth probe)
POSTFAST_PLATFORM_LABEL = {
    PLATFORM_TT: "TIKTOK",
    PLATFORM_IG: "INSTAGRAM",
}

# ---------------------------------------------------------------------------
# Bundle resolution
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_postfast_iso() -> str:
    """PostFast expects scheduledAt in ISO-8601 with millisecond precision + Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def resolve_bundle(case_id: str, info: dict) -> dict | None:
    """Return absolute paths to the MP4 + per-platform caption sidecars.

    Returns None (with stderr error) if any expected file is missing.
    """
    videos_dir = PROJECT_ROOT / info["videos_dir"]
    mp4 = videos_dir / f"{case_id}.mp4"
    ig_cap = videos_dir / f"{case_id}.ig_caption.txt"
    tt_cap = videos_dir / f"{case_id}.tt_caption.txt"

    missing = [str(p.relative_to(PROJECT_ROOT)) for p in (mp4, ig_cap, tt_cap) if not p.exists()]
    if missing:
        print(f"  ✗ {case_id}: missing bundle files: {', '.join(missing)}", file=sys.stderr)
        return None

    return {"mp4": mp4, "ig_caption": ig_cap, "tt_caption": tt_cap}


def pending_targets(info: dict, requested: Iterable[str]) -> list[str]:
    """Return the subset of `requested` platforms that still need posting for `info`.

    A platform is 'pending' if its tracker field is None (not posted, not skipped).
    """
    out = []
    for platform in requested:
        value = info.get(platform)
        if value is None:  # not yet posted, not skipped
            out.append(platform)
    return out


# ---------------------------------------------------------------------------
# PostFast HTTP client (stdlib only — keeps the dep surface tiny)
# ---------------------------------------------------------------------------


class PostFastConfig:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.environ.get("POSTFAST_API_KEY", "").strip()
        self.tt_account = os.environ.get("POSTFAST_TIKTOK_CHANNEL_ID", "").strip()
        self.ig_account = os.environ.get("POSTFAST_INSTAGRAM_CHANNEL_ID", "").strip()
        self.base_url = os.environ.get("POSTFAST_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    def social_media_id(self, platform: str) -> str:
        return self.tt_account if platform == PLATFORM_TT else self.ig_account

    def headers(self) -> dict[str, str]:
        return {
            "pf-api-key": self.api_key,
            "Accept": "application/json",
        }

    def assert_ready(self, platform: str | None = None) -> None:
        if not self.api_key:
            sys.exit("ERROR: POSTFAST_API_KEY missing from .env — see scripts/post_via_scheduler.py docstring.")
        if platform == PLATFORM_TT and not self.tt_account:
            sys.exit("ERROR: POSTFAST_TIKTOK_CHANNEL_ID missing — run --check-auth to find it.")
        if platform == PLATFORM_IG and not self.ig_account:
            sys.exit("ERROR: POSTFAST_INSTAGRAM_CHANNEL_ID missing — run --check-auth to find it.")


def _http_json(cfg: PostFastConfig, method: str, path: str,
               body: dict | None = None) -> tuple[int, dict | str]:
    """POST/GET JSON to PostFast. Returns (status, parsed_body_or_raw_text)."""
    url = f"{cfg.base_url}{path}"
    headers = cfg.headers()
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode(errors="replace")
            status = resp.status
    except urlerror.HTTPError as e:
        raw = e.read().decode(errors="replace") if hasattr(e, "read") else ""
        return e.code, raw
    except urlerror.URLError as e:
        return 0, f"URLError: {e.reason}"
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _s3_put_file(signed_url: str, mp4_path: Path) -> tuple[bool, str]:
    """PUT raw video bytes to the PostFast-issued S3 signed URL."""
    data = mp4_path.read_bytes()
    req = urlrequest.Request(
        signed_url,
        data=data,
        method="PUT",
        headers={"Content-Type": "video/mp4"},
    )
    try:
        with urlrequest.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            if 200 <= resp.status < 300:
                return True, f"S3 PUT {resp.status}"
            return False, f"S3 PUT {resp.status}"
    except urlerror.HTTPError as e:
        body = e.read().decode(errors="replace") if hasattr(e, "read") else ""
        return False, f"S3 HTTPError {e.code}: {body[:200]}"
    except urlerror.URLError as e:
        return False, f"S3 URLError: {e.reason}"
    except OSError as e:
        return False, f"S3 transport: {e}"


def postfast_check_auth(cfg: PostFastConfig) -> tuple[bool, list[dict] | str]:
    """Verify the key and list connected social accounts."""
    if not cfg.api_key:
        return False, "POSTFAST_API_KEY missing"
    status, body = _http_json(cfg, "GET", "/social-media/my-social-accounts")
    if status == 200 and isinstance(body, list):
        return True, body
    return False, f"HTTP {status}: {body if isinstance(body, str) else json.dumps(body)[:200]}"


def postfast_upload(
    cfg: PostFastConfig,
    platform: str,
    mp4_path: Path,
    caption: str,
) -> tuple[bool, str]:
    """3-step upload to PostFast for immediate publish to one platform.

    Returns (success, message). Schedules at "now" so PostFast publishes
    immediately (most schedulers treat 'now' as "publish ASAP").
    """
    cfg.assert_ready(platform)

    # Step 1: ask PostFast for a signed S3 upload URL
    status, body = _http_json(
        cfg, "POST", "/file/get-signed-upload-urls",
        {"contentType": "video/mp4", "count": 1},
    )
    if status >= 300 or not isinstance(body, (list, dict)):
        return False, f"signed-url HTTP {status}: {str(body)[:200]}"
    # PostFast returns either a list (per item) or a dict with an items array.
    record = None
    if isinstance(body, list) and body:
        record = body[0]
    elif isinstance(body, dict):
        # Try common shapes
        items = body.get("items") or body.get("urls") or body.get("data")
        if isinstance(items, list) and items:
            record = items[0]
        else:
            record = body
    if not isinstance(record, dict):
        return False, f"signed-url unexpected shape: {str(body)[:200]}"
    signed_url = record.get("signedUrl") or record.get("url")
    s3_key = record.get("key") or record.get("fileKey")
    if not signed_url or not s3_key:
        return False, f"signed-url missing fields: {str(record)[:200]}"

    # Step 2: PUT the MP4 to S3
    ok, msg = _s3_put_file(signed_url, mp4_path)
    if not ok:
        return False, msg

    # Step 3: create the post
    controls: dict = {}
    if platform == PLATFORM_TT:
        controls["tiktokPrivacy"] = "PUBLIC_TO_EVERYONE"
        controls["tiktokAllowDuet"] = True
        controls["tiktokAllowStitch"] = True
        controls["tiktokAllowComment"] = True
    elif platform == PLATFORM_IG:
        controls["instagramPublishType"] = "REEL"

    post_payload = {
        "posts": [
            {
                "content": caption,
                "mediaItems": [
                    {
                        "key": s3_key,
                        "type": "VIDEO",
                        "sortOrder": 0,
                        "coverTimestamp": "1000",
                    }
                ],
                "scheduledAt": _now_postfast_iso(),
                "socialMediaId": cfg.social_media_id(platform),
                "controls": controls,
            }
        ]
    }
    status, body = _http_json(cfg, "POST", "/social-posts", post_payload)
    if 200 <= status < 300:
        # PostFast returns either {data:[{id,...}]} or {posts:[{...}]} or bare {id,...}
        post_id = "?"
        if isinstance(body, dict):
            for container_key in ("data", "posts"):
                container = body.get(container_key)
                if isinstance(container, list) and container and isinstance(container[0], dict):
                    post_id = container[0].get("id", post_id)
                    break
            if post_id == "?":
                post_id = body.get("id") or body.get("post_id") or "?"
        elif isinstance(body, list) and body and isinstance(body[0], dict):
            post_id = body[0].get("id", "?")
        return True, f"queued (post_id={post_id})"
    return False, f"create-post HTTP {status}: {str(body)[:200]}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def post_case(
    case_id: str,
    state: dict[str, dict],
    cfg: PostFastConfig,
    requested_platforms: Iterable[str],
    dry_run: bool = False,
) -> dict[str, str]:
    """Post one case to its pending platforms. Returns {platform: result_msg}."""
    info = state.get(case_id)
    if not info:
        return {"_error": f"{case_id} not in tracker; run cross_post_status.py --refresh"}

    pending = pending_targets(info, requested_platforms)
    if not pending:
        return {"_skip": f"{case_id}: nothing pending on {','.join(requested_platforms)}"}

    bundle = resolve_bundle(case_id, info)
    if not bundle:
        return {"_error": f"{case_id}: bundle missing"}

    results: dict[str, str] = {}
    for platform in pending:
        caption_path = bundle["tt_caption"] if platform == PLATFORM_TT else bundle["ig_caption"]
        caption = caption_path.read_text().strip()
        if not caption:
            results[platform] = "skip: empty caption"
            continue

        if dry_run:
            results[platform] = (
                f"DRY-RUN: would upload {bundle['mp4'].relative_to(PROJECT_ROOT)} "
                f"({bundle['mp4'].stat().st_size // 1024} KB), caption[{len(caption)}c]"
            )
            continue

        # Defensive: skip platforms without an account configured
        if not cfg.social_media_id(platform):
            results[platform] = f"skip: no POSTFAST_{platform.upper()}_CHANNEL_ID set"
            continue

        ok, msg = postfast_upload(cfg, platform, bundle["mp4"], caption)
        if ok:
            # Mark in tracker immediately so a crash mid-batch doesn't double-post
            info[platform] = _now_iso()
            save_status(state)
            results[platform] = f"✓ {msg}"
            time.sleep(THROTTLE_SECONDS)
        else:
            results[platform] = f"✗ {msg}"

    return results


def select_cases(
    state: dict[str, dict],
    case_filter: str | None,
    requested_platforms: Iterable[str],
) -> list[str]:
    """Return case_ids to operate on, sorted by tracker order."""
    if case_filter:
        if case_filter not in state:
            sys.exit(f"ERROR: case '{case_filter}' not in tracker; run cross_post_status.py --refresh.")
        return [case_filter]

    # --all-pending mode: any case with at least one requested platform pending
    out = []
    for case_id, info in sorted(state.items()):
        if pending_targets(info, requested_platforms):
            out.append(case_id)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--all-pending", action="store_true",
                   help="Queue every case with at least one pending platform")
    g.add_argument("--case", help="One case_id (e.g. SY_05_H_basement)")
    g.add_argument("--check-auth", action="store_true",
                   help="Probe the API key and list connected accounts (surfaces social_media_id values)")

    parser.add_argument("--platforms", choices=("tt", "ig", "both"), default="both",
                        help="Which platforms to target (default: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't call PostFast; just print what would happen")
    args = parser.parse_args()

    cfg = PostFastConfig()

    if args.check_auth:
        ok, body = postfast_check_auth(cfg)
        if not ok:
            print(f"  ✗ {body}")
            return 1
        accounts = body  # list of dicts
        if not accounts:
            print(f"  ✓ Key valid but no connected accounts. Connect TikTok or Instagram in PostFast dashboard.")
            return 0
        print(f"  ✓ Key valid. {len(accounts)} connected account(s):\n")
        for acct in accounts:
            label = acct.get("platform", "?")
            uname = acct.get("platformUsername") or acct.get("displayName") or "?"
            sm_id = acct.get("id", "?")
            print(f"    {label:<10}  @{uname:<24}  social_media_id={sm_id}")
        print()
        # Helpful hint if .env values diverge from connected accounts
        env_map = {
            PLATFORM_TT: cfg.tt_account,
            PLATFORM_IG: cfg.ig_account,
        }
        for plat_key, label in POSTFAST_PLATFORM_LABEL.items():
            envval = env_map[plat_key]
            matches = [a for a in accounts if a.get("platform") == label]
            if not matches:
                if envval:
                    print(f"  ⚠  .env has POSTFAST_{plat_key.upper()}_CHANNEL_ID set but no {label} account is connected.")
                continue
            ids = [a.get("id") for a in matches]
            if not envval:
                print(f"  ℹ  {label} connected but POSTFAST_{plat_key.upper()}_CHANNEL_ID empty in .env.")
                print(f"     Add: POSTFAST_{plat_key.upper()}_CHANNEL_ID={ids[0]}")
            elif envval not in ids:
                print(f"  ⚠  POSTFAST_{plat_key.upper()}_CHANNEL_ID={envval} doesn't match any connected {label} id ({ids}).")
        return 0

    # Load + refresh tracker (no-op for already-tracked cases).
    # `refresh_from_posted_ledgers` may also back-fill `tiktok_gate` on existing
    # entries (see cross_post_status.py:160-165), so save unconditionally — we
    # were silently dropping those mutations when the new-case count was 0.
    state = load_status()
    refresh_from_posted_ledgers(state)
    save_status(state)

    requested = PLATFORM_CLI_MAP[args.platforms]
    cases = select_cases(state, args.case, requested)
    if not cases:
        print(f"  ✓ Nothing pending on {','.join(requested)}.")
        return 0

    print(f"  Queue: {len(cases)} case(s) → {','.join(requested)} via PostFast"
          f"{' (dry-run)' if args.dry_run else ''}")

    n_ok = 0
    n_fail = 0
    n_skip = 0
    for case_id in cases:
        results = post_case(case_id, state, cfg, requested, dry_run=args.dry_run)
        for platform, msg in results.items():
            if platform.startswith("_"):
                # _error or _skip pseudo-keys
                tag = "·" if platform == "_skip" else "✗"
                print(f"  {tag} {msg}")
                if platform == "_skip":
                    n_skip += 1
                else:
                    n_fail += 1
                continue
            print(f"  {case_id} [{platform}] {msg}")
            if msg.startswith("✓") or msg.startswith("DRY-RUN"):
                n_ok += 1
            elif msg.startswith("✗"):
                n_fail += 1
            else:
                n_skip += 1

    print(f"\n  Done: {n_ok} ok, {n_fail} failed, {n_skip} skipped")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
