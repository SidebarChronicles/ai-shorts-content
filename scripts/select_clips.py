#!/usr/bin/env python3
"""Select and extract 4 clip segments from a game trailer.

Two modes:
  --auto        FFmpeg scene detection → distribute 4 clips across trailer zones
  --clips JSON  Manual timestamp spec (Justin watches trailer, provides timestamps)

Usage:
    python scripts/select_clips.py --game-id GG_01_elden_ring --auto
    python scripts/select_clips.py --game-id GG_01_elden_ring \\
      --clips '[{"start":10,"end":22,"label":"hook"},{"start":35,"end":47,"label":"gameplay"},{"start":60,"end":72,"label":"standout"},{"start":85,"end":95,"label":"cta"}]'

Output:
    output/scripts/<game_id>/clips/clip_01.mp4 … clip_04.mp4
    output/scripts/<game_id>/clips_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

BEAT_LABELS = ["hook", "gameplay", "standout", "cta"]
TARGET_CLIP_LEN = 11  # seconds per clip (target)
MIN_CLIP_LEN = 8
MAX_CLIP_LEN = 14

# Zone centers as fraction of total duration
ZONE_CENTERS = [0.20, 0.40, 0.60, 0.82]


# ---------------------------------------------------------------------------
# Trailer duration
# ---------------------------------------------------------------------------

def get_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: ffprobe failed on {path}: {result.stderr}")
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# Scene detection
# ---------------------------------------------------------------------------

def detect_scene_changes(trailer: Path, threshold: float = 0.35) -> list[float]:
    """Run FFmpeg scene detection, return sorted list of scene-change timestamps."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(trailer),
            "-vf", f"select=gt(scene\\,{threshold}),showinfo",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=120,
    )
    # Parse pts_time values from stderr
    timestamps = []
    for match in re.finditer(r"pts_time:([\d.]+)", result.stderr):
        timestamps.append(float(match.group(1)))

    timestamps.sort()
    return timestamps


def auto_select_clips(changes: list[float], total_duration: float) -> list[dict]:
    """Pick 4 clips distributed across 4 zones of the trailer."""
    clips = []

    for i, (zone_center, label) in enumerate(zip(ZONE_CENTERS, BEAT_LABELS)):
        target_time = zone_center * total_duration

        # Find the nearest scene change to this zone center
        if changes:
            nearest = min(changes, key=lambda t: abs(t - target_time))
        else:
            nearest = target_time

        # Clip start: at the nearest scene change (or target if no changes)
        start = max(0.0, nearest)

        # Ensure clip doesn't go into the next zone's territory
        max_end = ZONE_CENTERS[i + 1] * total_duration if i + 1 < len(ZONE_CENTERS) else total_duration
        end = min(start + TARGET_CLIP_LEN, max_end - 1.0, total_duration - 0.5)

        # Ensure minimum clip length
        if end - start < MIN_CLIP_LEN:
            start = max(0.0, end - TARGET_CLIP_LEN)

        clips.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "label": label,
        })

    return clips


# ---------------------------------------------------------------------------
# Clip extraction
# ---------------------------------------------------------------------------

def extract_clip(trailer: Path, start: float, end: float, out_path: Path) -> None:
    """Extract a clip segment using stream copy (no re-encode at this stage)."""
    duration = end - start
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(trailer),
            "-t", str(duration),
            "-c", "copy",
            str(out_path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: ffmpeg extraction failed for {out_path.name}:\n{result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Select and extract 4 clips from a game trailer.")
    parser.add_argument("--game-id", required=True, metavar="ID", help="Game ID")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--auto", action="store_true", help="Auto scene detection mode")
    mode.add_argument("--clips", metavar="JSON",
                      help='JSON array: [{"start":N,"end":N,"label":"hook"}, ...]')
    parser.add_argument("--threshold", type=float, default=0.35,
                        help="Scene detection threshold 0–1 (default 0.35)")
    args = parser.parse_args()

    game_dir = SCRIPTS_DIR / args.game_id
    trailer_path = game_dir / "trailer_raw.mp4"

    if not trailer_path.exists():
        sys.exit(
            f"ERROR: No trailer found at {trailer_path}\n"
            f"Run: python scripts/fetch_trailer.py --game-id {args.game_id} --steam <id>"
        )

    print(f"── Select Clips: {args.game_id} ──")

    total_duration = get_duration(trailer_path)
    print(f"  Trailer duration: {total_duration:.1f}s")

    if total_duration < 20:
        sys.exit(
            f"ERROR: Trailer is only {total_duration:.1f}s long — need at least 20s "
            f"to extract 4 portrait clips. The trailer file may be corrupt or truncated."
        )

    if args.auto:
        print(f"  Running scene detection (threshold={args.threshold})…")
        changes = detect_scene_changes(trailer_path, args.threshold)
        print(f"  Found {len(changes)} scene changes")
        # Sanity: an empty/corrupt trailer produces zero detections; we'd then
        # extract four near-identical clips and silently ship a useless video.
        if len(set(changes)) < 2:
            sys.exit(
                "ERROR: Scene detection found fewer than 2 distinct timestamps. "
                "Trailer likely corrupt — delete trailer_raw.mp4 and re-fetch."
            )
        clip_specs = auto_select_clips(changes, total_duration)
        print("  Auto-selected clips:")
        for spec in clip_specs:
            print(f"    {spec['label']:12s} {spec['start']:.1f}s → {spec['end']:.1f}s "
                  f"({spec['end']-spec['start']:.1f}s)")
    else:
        try:
            clip_specs = json.loads(args.clips)
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: Invalid --clips JSON: {e}")

        # Validate
        for spec in clip_specs:
            for key in ("start", "end", "label"):
                if key not in spec:
                    sys.exit(f"ERROR: Each clip spec must have 'start', 'end', 'label'. Missing: {key}")
            if spec["end"] > total_duration:
                print(f"  ⚠  Clip '{spec['label']}' end={spec['end']} exceeds trailer duration {total_duration:.1f}s — clamping")
                spec["end"] = total_duration

    # Extract clips
    clips_dir = game_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, spec in enumerate(clip_specs, 1):
        label = spec.get("label", BEAT_LABELS[i - 1])
        out_path = clips_dir / f"clip_{i:02d}.mp4"
        duration = spec["end"] - spec["start"]

        print(f"  Extracting clip_{i:02d} ({label})… ", end="", flush=True)
        extract_clip(trailer_path, spec["start"], spec["end"], out_path)
        print(f"✓ ({duration:.1f}s)")

        manifest.append({
            "file": str(out_path.relative_to(PROJECT_ROOT)),
            "start": spec["start"],
            "end": spec["end"],
            "duration": round(duration, 2),
            "label": label,
        })

    # Save manifest
    manifest_path = game_dir / "clips_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n  ✓ Manifest: {manifest_path.relative_to(PROJECT_ROOT)}")

    total_clip_duration = sum(c["duration"] for c in manifest)
    print(f"  Total clip duration: {total_clip_duration:.1f}s")
    if total_clip_duration < 38:
        print("  ⚠  Total clips < 38s — may be too short for a 40–50s short. Consider longer clips.")

    print(f"\n  Next: write output/scripts/{args.game_id}/game_config.json + generate script")
    print(f"  Then: python skill/game-short/render_game_video.py output/scripts/{args.game_id}/game_config.json")


if __name__ == "__main__":
    main()
