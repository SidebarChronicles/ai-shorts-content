#!/usr/bin/env python3
"""Mix narration + background music + transition SFX into a final audio track.

Research benchmark (Virvid 200-video study): videos with music (-22dB ducked)
+ whoosh SFX at every cut retained 71% on average, vs 48% for narration-only.

This script reads:
  - narration MP3 (anchor, 0 dB) from assets/audio/narration_<case>.mp3
  - vertical-matched music loop from assets/music/<vertical>/<track>.mp3
  - per-cut transition SFX from assets/sfx/whoosh_*.wav
  - alignment.json (for the 30s mid-anchor silence dropout)
  - bg_clips_concat.txt (for the cut timestamps where SFX go)

Produces: output/scripts/<case>/audio_mixed.mp3 (gitignored)

The final FFmpeg encode in render_game_video.py uses this mixed audio
instead of the bare narration.

Usage:
    python scripts/build_audio_track.py --case GG_07_marathon
    python scripts/build_audio_track.py --case 01_gothferrari --music-vertical cases
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
MUSIC_DIR = PROJECT_ROOT / "assets" / "music"
SFX_DIR = PROJECT_ROOT / "assets" / "sfx"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

# Mix levels (dB relative to the narration anchor)
NARRATION_DB = 0
MUSIC_DB = -22
SFX_DB = -16

# Vertical detection from case_id prefix → music subfolder
VERTICAL_MUSIC_MAP = {
    "GG_": "games",
    "MV_": "movies",
    "MY_": "mythology",
    "UM_": "mysteries",
    "TX_": "games",  # Top X is gaming-adjacent
    "FN_": "finance",
}
DEFAULT_MUSIC_VERTICAL = "cases"  # numeric prefixes (01_, 02_, ...) = cases

# Story sub-genre → music vertical override. Story IDs are SY_NN_<S|R|H>_<slug>.
# Survival + horror need menacing/tension music; Reddit dramatizations sit
# closer to neutral suspense (cases folder).
STORY_SUBGENRE_MUSIC = {
    "S": "mysteries",  # survival — atmospheric dread
    "H": "mysteries",  # horror — same, swap to a dedicated horror/ folder once seeded
    "R": "cases",      # Reddit dramatization — neutral suspense
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_vertical(case_id: str) -> str:
    """Map case_id prefix to music subfolder name."""
    # Story vertical first: sub-genre letter determines tonal palette
    if case_id.startswith("SY_"):
        # SY_NN_<S|R|H>_<slug>
        parts = case_id.split("_")
        if len(parts) >= 3 and parts[2] in STORY_SUBGENRE_MUSIC:
            return STORY_SUBGENRE_MUSIC[parts[2]]
        return "mysteries"  # fallback if parse fails
    for prefix, vertical in VERTICAL_MUSIC_MAP.items():
        if case_id.startswith(prefix):
            return vertical
    return DEFAULT_MUSIC_VERTICAL


def pick_music_track(vertical: str) -> Path | None:
    """Pick a random music track from the vertical's subfolder."""
    subfolder = MUSIC_DIR / vertical
    if not subfolder.exists():
        return None
    tracks = list(subfolder.glob("*.mp3")) + list(subfolder.glob("*.wav"))
    if not tracks:
        return None
    return random.choice(tracks)


def pick_sfx() -> Path | None:
    """Legacy single-pick — kept for backwards compat. Per-vertical selection
    happens in pick_sfx_for_beat() below."""
    if not SFX_DIR.exists():
        return None
    sfx_files = list(SFX_DIR.glob("whoosh*.wav")) + list(SFX_DIR.glob("whoosh*.mp3"))
    if not sfx_files:
        return None
    return random.choice(sfx_files)


# ---------------------------------------------------------------------------
# Per-vertical SFX selection
# ---------------------------------------------------------------------------

# Map case_id prefix → SFX subfolder. Story sub-genres (S/R/H) get their own
# folders; other verticals map to single folder names.
SFX_VERTICAL_MAP = {
    "GG_": "games",
    "MV_": "movies",
    "MY_": "mythology",
    "UM_": "mysteries",
    "TX_": "topx",
    "FN_": "finance",
}
DEFAULT_SFX_VERTICAL = "cases"

# Story sub-genre letter → SFX subfolder
STORY_SFX_MAP = {
    "S": "story_survival",
    "R": "story_reddit",
    "H": "story_horror",
}

# Category prefix → category name. Used by pick_sfx_for_beat to vary across
# 5 SFX placements (no two adjacent picks should share a category).
SFX_CATEGORIES = ("whoosh", "sting", "riser", "drop", "atmos")


def detect_sfx_vertical(case_id: str) -> str:
    """Map case_id to the assets/sfx/<vertical>/ folder name."""
    if case_id.startswith("SY_"):
        parts = case_id.split("_")
        if len(parts) >= 3 and parts[2] in STORY_SFX_MAP:
            return STORY_SFX_MAP[parts[2]]
        return "story_survival"  # fallback
    for prefix, vertical in SFX_VERTICAL_MAP.items():
        if case_id.startswith(prefix):
            return vertical
    return DEFAULT_SFX_VERTICAL


def _categorize_sfx(path: Path) -> str:
    """Infer category from filename prefix (e.g. whoosh_basic_01.wav → 'whoosh')."""
    stem = path.stem.lower()
    for cat in SFX_CATEGORIES:
        if stem.startswith(cat):
            return cat
    return "other"


def pick_sfx_for_beat(slot_idx: int, n_slots: int, case_id: str,
                      prev_paths: list[Path], seed: int | None = None) -> Path | None:
    """Pick a varied SFX for slot_idx of n_slots total, based on case_id's vertical.

    Rules:
      - Slot 0 (opener)   → prefer sting or whoosh (attention)
      - Slot N-1 (closer) → prefer drop or sting (punctuation)
      - Middle slots      → rotate across whoosh / riser / atmos
      - Story horror      → bias 30% toward riser/atmos at any slot
      - Never the same file twice in a row
      - Fall back to _shared/ if the vertical folder is empty
    """
    vertical = detect_sfx_vertical(case_id)
    vertical_dir = SFX_DIR / vertical
    shared_dir = SFX_DIR / "_shared"

    # Walk both dirs; vertical-specific files take priority
    pool: list[Path] = []
    if vertical_dir.exists():
        pool.extend(sorted(vertical_dir.glob("*.wav")))
        pool.extend(sorted(vertical_dir.glob("*.mp3")))
    if shared_dir.exists():
        pool.extend(sorted(shared_dir.glob("*.wav")))
        pool.extend(sorted(shared_dir.glob("*.mp3")))
    if not pool:
        return None

    # Categorize the pool
    by_cat: dict[str, list[Path]] = {}
    for p in pool:
        by_cat.setdefault(_categorize_sfx(p), []).append(p)

    # Decide preferred categories for this slot
    is_horror = vertical == "story_horror"
    if slot_idx == 0:
        prefs = ["sting", "whoosh"]
    elif slot_idx == n_slots - 1:
        prefs = ["drop", "sting", "whoosh"]
    else:
        prefs = ["whoosh", "riser", "atmos"]

    # Horror bias: 30% chance to inject riser/atmos at any slot
    if is_horror and random.random() < 0.30:
        prefs = ["riser", "atmos"] + prefs

    # Excluded files: last 2 picks (no immediate repeats)
    excluded = set(prev_paths[-2:])

    # Try each preferred category until we find a non-excluded file
    for cat in prefs:
        candidates = [p for p in by_cat.get(cat, []) if p not in excluded]
        if candidates:
            return random.choice(candidates)

    # No category-preferred match → any non-excluded file from the whole pool
    candidates = [p for p in pool if p not in excluded]
    if candidates:
        return random.choice(candidates)
    # Worst case (small pool, all excluded): allow repeat
    return random.choice(pool)


def get_narration_duration(narration_path: Path) -> float:
    """ffprobe wrapper."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(narration_path)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: ffprobe failed on {narration_path}")
    return float(result.stdout.strip())


def parse_cut_timestamps(concat_path: Path) -> list[float]:
    """Read bg_clips_concat.txt → cumulative timestamps of cut boundaries.

    Skips the first clip (no cut at t=0) and the duplicated final entry that
    FFmpeg's concat demuxer requires. Returns the seconds at which each
    subsequent clip starts — exactly where we want a whoosh SFX.
    """
    if not concat_path.exists():
        return []
    durations = []
    for line in concat_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("duration "):
            try:
                durations.append(float(line.split()[1]))
            except (ValueError, IndexError):
                pass
    if not durations:
        # build_visuals_track.py-style: file lines only, no duration directives.
        # Each clip in the file is its own entry; probe each for duration.
        files = []
        for line in concat_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("file "):
                # 'file /abs/path/clip.mp4'
                p = line[5:].strip(" '\"")
                files.append(Path(p))
        for f in files:
            if f.exists():
                durations.append(get_narration_duration(f))
    # cut boundaries are cumulative sums of durations (skip the first 0)
    cumulative = []
    running = 0.0
    for d in durations[:-1]:  # exclude last segment so we don't put SFX at the very end
        running += d
        cumulative.append(running)
    return cumulative


# ---------------------------------------------------------------------------
# Mixer
# ---------------------------------------------------------------------------

def build_mix(narration: Path, music: Path | None, sfx_cuts: list[tuple[float, Path]],
              total_dur: float, mid_anchor_time: float | None,
              out_path: Path, dry_run: bool = False) -> None:
    """Mix narration + ducked music + SFX bursts at cut timestamps.

    Filter graph strategy:
      [0]anull        → narration anchor (0 dB)
      [1]music        → volume scaled to MUSIC_DB; if mid_anchor_time given, apply 0.5s gate at that point
      [2..N]sfx       → each delayed to its cut timestamp, volume -16 dB
      amix all together with weights so narration dominates

    Music ducking under narration is handled implicitly: the music sits ~22dB
    below the narration. We do NOT use sidechaincompress here because it adds
    pumping artifacts; static -22dB attenuation is cleaner for narration-heavy
    Shorts (research-confirmed in NARRATION_BOX 2025 guide).
    """
    inputs = ["-i", str(narration)]
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]

    # Build filter pieces
    filters = []
    n_input_idx = 0

    # Narration: keep at 0 dB
    filters.append(f"[{n_input_idx}:a]volume=1.0[narration]")

    label_count = 1  # we'll mix [narration] + others
    mix_labels = ["[narration]"]

    if music:
        n_input_idx += 1
        # Music: scale down, trim to total duration
        # If we have a mid_anchor_time, add a 0.5s silence right at that mark
        # by using volume=0.0 envelope: enable='between(t,a,b)'
        music_filter = f"[{n_input_idx}:a]volume={10**(MUSIC_DB/20):.4f}"
        if mid_anchor_time is not None and 0 < mid_anchor_time < total_dur - 0.5:
            # Add a duck-to-silence envelope around the mid-anchor
            music_filter += (
                f",volume=enable='between(t,{mid_anchor_time:.2f},{mid_anchor_time+0.5:.2f})':volume=0.0"
            )
        music_filter += f",atrim=duration={total_dur:.2f}[music]"
        filters.append(music_filter)
        mix_labels.append("[music]")

    # SFX bursts at each cut timestamp
    for t, sfx_path in sfx_cuts:
        n_input_idx += 1
        inputs += ["-i", str(sfx_path)]
        # adelay needs ms; both channels
        delay_ms = int(t * 1000)
        sfx_label = f"sfx_{len(mix_labels)}"
        filters.append(
            f"[{n_input_idx}:a]volume={10**(SFX_DB/20):.4f},adelay={delay_ms}|{delay_ms}[{sfx_label}]"
        )
        mix_labels.append(f"[{sfx_label}]")

    # Mix them all — duration=first means we cut to narration length
    mix = "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=first:normalize=0[out]"
    filters.append(mix)

    filter_complex = ";".join(filters)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]

    if dry_run:
        print("  [dry-run] would run:", " ".join(cmd[:6]), "...")
        return

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # Show last 600 chars of stderr for debug
        sys.exit(f"ERROR: ffmpeg mix failed:\n{result.stderr[-600:]}")


# ---------------------------------------------------------------------------
# Mid-anchor detection from alignment.json
# ---------------------------------------------------------------------------

def find_mid_anchor_time(case_id: str) -> float | None:
    """Try to find the timestamp where beat 4 (the mid-anchor) starts.

    Fallbacks:
      - If config has 7+ beats: use beat index 3 (the mid_anchor by convention)
      - If config has 4-6 beats: midpoint of audio
      - If no alignment: None
    """
    alignment_path = AUDIO_DIR / f"narration_{case_id}.alignment.json"
    if not alignment_path.exists():
        return None
    try:
        alignment = json.loads(alignment_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    total_dur = alignment["character_end_times_seconds"][-1]

    # Find config
    cfg = None
    for filename in ("script_config.json", "game_config.json"):
        p = SCRIPTS_DIR / case_id / filename
        if p.exists():
            try:
                cfg = json.loads(p.read_text())
                break
            except (json.JSONDecodeError, OSError):
                pass
    if cfg is None:
        return total_dur / 2

    beats = cfg.get("beats", [])
    if len(beats) >= 7:
        # 7-beat structure: beat 4 is the mid_anchor (index 3)
        spoken = "".join(alignment["characters"])
        starts = alignment["character_start_times_seconds"]
        position = 0
        for i, b in enumerate(beats):
            text = b.get("text", "")
            idx = spoken.find(text, position)
            if idx == -1:
                idx = spoken.find(text[:20], position)
            if i == 3 and idx >= 0:
                return starts[idx]
            if idx >= 0:
                position = idx + len(text)
        return total_dur / 2

    # Older 4-beat structures: just use the midpoint
    return total_dur / 2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="Case ID (matches output/scripts/<case>/)")
    parser.add_argument("--music-vertical", default=None,
                        help="Override the music subfolder (games/movies/cases/mythology/mysteries/finance)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for music + SFX selection")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-sfx", action="store_true", help="Skip transition SFX bursts")
    parser.add_argument("--no-music", action="store_true", help="Skip background music")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    case_dir = SCRIPTS_DIR / args.case
    narration = AUDIO_DIR / f"narration_{args.case}.mp3"
    if not narration.exists():
        sys.exit(f"ERROR: narration not found: {narration}\n"
                 f"Run: python scripts/make_audio_elevenlabs.py --case {args.case}")

    total_dur = get_narration_duration(narration)
    vertical = args.music_vertical or detect_vertical(args.case)

    print(f"── Audio mix: {args.case} ──")
    print(f"  Narration:  {narration.name}  ({total_dur:.1f}s)")
    print(f"  Vertical:   {vertical}")

    # Music
    music = None
    if not args.no_music:
        music = pick_music_track(vertical)
        if music:
            print(f"  Music:      {music.relative_to(MUSIC_DIR)}  @ {MUSIC_DB}dB")
        else:
            print(f"  Music:      ✗ no track in assets/music/{vertical}/ — skipping (run scripts/seed_audio_assets.py)")

    # Mid-anchor silence window
    mid_anchor = find_mid_anchor_time(args.case)
    if mid_anchor is not None and music is not None:
        print(f"  Silence:    {mid_anchor:.1f}s → {mid_anchor+0.5:.1f}s (mid-anchor dropout)")

    # SFX at cut timestamps — capped to MAX_SFX_PER_VIDEO and spaced ≥4s apart
    # so we get punchy emphasis, not a relentless whoosh-every-cut soundtrack.
    # Per-vertical SFX selection with category variety: see pick_sfx_for_beat.
    MAX_SFX_PER_VIDEO = 5
    MIN_SFX_SPACING_SECONDS = 4.0
    sfx_cuts: list[tuple[float, Path]] = []
    if not args.no_sfx:
        concat = case_dir / "bg_clips_concat.txt"
        cut_times = parse_cut_timestamps(concat)
        # Sanity check: any SFX files anywhere under assets/sfx/?
        any_sfx = list(SFX_DIR.rglob("*.wav")) + list(SFX_DIR.rglob("*.mp3")) if SFX_DIR.exists() else []
        if any_sfx and cut_times:
            # Filter to a sparse subset: keep cuts ≥4s apart, cap at 5 total
            sparse_cuts: list[float] = []
            last_t = -MIN_SFX_SPACING_SECONDS
            for t in cut_times:
                if t - last_t >= MIN_SFX_SPACING_SECONDS:
                    sparse_cuts.append(t)
                    last_t = t
                if len(sparse_cuts) >= MAX_SFX_PER_VIDEO:
                    break
            # Per-vertical, category-varied SFX selection
            picked_paths: list[Path] = []
            sfx_vertical = detect_sfx_vertical(args.case)
            for slot_idx, t in enumerate(sparse_cuts):
                sfx_path = pick_sfx_for_beat(
                    slot_idx=slot_idx,
                    n_slots=len(sparse_cuts),
                    case_id=args.case,
                    prev_paths=picked_paths,
                )
                if sfx_path:
                    sfx_cuts.append((t, sfx_path))
                    picked_paths.append(sfx_path)
            # Pretty-print which file went where
            picks_str = ", ".join(
                f"{t:.1f}s={p.parent.name}/{p.stem}"
                for t, p in sfx_cuts
            )
            print(f"  SFX:        {len(sfx_cuts)}/{len(cut_times)} (vertical={sfx_vertical}, "
                  f"spaced ≥{MIN_SFX_SPACING_SECONDS}s, cap {MAX_SFX_PER_VIDEO}) @ {SFX_DB}dB")
            print(f"              → {picks_str}")
        else:
            why = "no concat list" if not cut_times else "no SFX files in assets/sfx/"
            print(f"  SFX:        ✗ {why} — skipping (run scripts/seed_sfx_assets.py)")

    out_path = case_dir / "audio_mixed.mp3"
    print(f"\n  Mixing…")
    build_mix(narration, music, sfx_cuts, total_dur, mid_anchor, out_path, dry_run=args.dry_run)
    if not args.dry_run:
        out_size = out_path.stat().st_size
        print(f"  ✓ {out_path.relative_to(PROJECT_ROOT)}  ({out_size//1024} KB)")


if __name__ == "__main__":
    main()
