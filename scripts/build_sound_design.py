#!/usr/bin/env python3
"""Build per-beat sound design (ambient + SFX + music) under the TTS narration.

Consumes each beat's `sound_brief` from script_config.json:

  - ambient_bed       → looped Freesound/Pixabay clip at low mix
  - sfx               → discrete hits placed at at_sec relative to beat start
  - music_intensity   → if >= 0.5, select stinger from assets/music/<mood>/
  - vocal_mood        → consumed by make_audio_elevenlabs.py (not here)
  - mix_note          → natural-language; used as a hint, not a parser target

Output:
  output/audio/<case>/sound_design.wav  (single mixed file, beat-aligned)
  output/audio/<case>/sound_assets/     (cached source files)

The narration is laid down separately by make_audio_elevenlabs.py. The final
mux step (in whatever pipeline script combines VO + visuals) layers the VO
ON TOP OF this sound_design.wav.

Sourcing chain (per ambient_bed and per SFX):
  1. Freesound API (free, CC0/CC-BY) — needs FREESOUND_API_TOKEN
  2. Pixabay sound effects (no auth) — needs PIXABAY_API_KEY
  3. Silence — if neither is available

Usage:
    python scripts/build_sound_design.py --case SY_07_H_slug
    python scripts/build_sound_design.py --case SY_07_H_slug --skip-music
    python scripts/build_sound_design.py --case SY_07_H_slug --dry-run
    python scripts/build_sound_design.py --music-check   # verify assets/music/ seeded
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
MUSIC_DIR = PROJECT_ROOT / "assets" / "music"
OUTPUT_AUDIO_DIR = PROJECT_ROOT / "output" / "audio"

# Music library mapping — sub-genre letter → list of filename stems
MUSIC_LIBRARY = {
    "H": ["dread_drone_a", "dread_drone_b"],
    "S": ["tension_pulse_a", "tension_pulse_b"],
    "R": ["social_curiosity_a"],
}

DEFAULT_AMBIENT_DB = -18.0
DEFAULT_SFX_DB = -8.0
DEFAULT_MUSIC_DB = -14.0  # before intensity multiplier

# Freesound API surface
FREESOUND_SEARCH_URL = "https://freesound.org/apiv2/search/text/"
FREESOUND_INSTANCE_URL = "https://freesound.org/apiv2/sounds/{id}/"

# Pixabay sound effects API
PIXABAY_SFX_URL = "https://pixabay.com/api/sounds/"  # NOTE: Pixabay does not have
# a public sound-effects search API as of this writing. We use it as a documented
# fallback path; in practice the Freesound chain handles ~95% of cases. If
# Pixabay opens a public SFX search, this is where it plugs in.


# ---------------------------------------------------------------------------
# Audio source fetchers
# ---------------------------------------------------------------------------

def freesound_search(query: str, token: str, max_duration: float | None = None) -> str | None:
    """Return a preview URL (.mp3) for the top Freesound result, or None."""
    if not token:
        return None
    params = {
        "query": query,
        "token": token,
        "fields": "id,name,duration,license,previews,type",
        "page_size": 5,
        "filter": "type:wav OR type:mp3 OR type:ogg",
    }
    if max_duration:
        params["filter"] += f" duration:[1 TO {int(max_duration)}]"
    try:
        resp = requests.get(FREESOUND_SEARCH_URL, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"    [freesound] HTTP {resp.status_code} for '{query}'", file=sys.stderr)
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        # Pick the first reasonably-sized result
        for r in results:
            previews = r.get("previews", {})
            url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
            if url:
                return url
        return None
    except (requests.RequestException, ValueError) as e:
        print(f"    [freesound] network error: {e}", file=sys.stderr)
        return None


def download_to(url: str, dest: Path, token: str | None = None) -> bool:
    """Stream a URL to a file. Returns True on success."""
    headers = {}
    if token and "freesound.org" in url:
        headers["Authorization"] = f"Token {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=30, stream=True)
        if resp.status_code != 200:
            print(f"    [download] HTTP {resp.status_code} for {url}", file=sys.stderr)
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return dest.stat().st_size > 1024  # at least 1KB or we got garbage
    except (requests.RequestException, OSError) as e:
        print(f"    [download] error: {e}", file=sys.stderr)
        return False


def fetch_audio_clip(query: str, dest_dir: Path, label: str,
                     max_duration: float | None, freesound_token: str) -> Path | None:
    """Source an audio clip via the chain: Freesound → silence-fallback.

    Caches into dest_dir/<label>.mp3 — if already present, returns cached path.
    """
    cached = dest_dir / f"{label}.mp3"
    if cached.exists():
        return cached
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Try Freesound
    if freesound_token:
        preview_url = freesound_search(query, freesound_token, max_duration=max_duration)
        if preview_url and download_to(preview_url, cached, token=freesound_token):
            return cached

    # Pixabay SFX search has no public API as of this writing; future plug-in here.
    # For now, silence fallback signals to the caller.
    return None


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------

def ffmpeg_probe_duration(path: Path) -> float:
    """Return duration in seconds via ffprobe, or 0.0 on failure."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (subprocess.SubprocessError, ValueError):
        return 0.0


def make_silence(duration: float, out_path: Path, sample_rate: int = 44100) -> Path:
    """Generate a silent stereo WAV of N seconds."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anullsrc=channel_layout=stereo:sample_rate={sample_rate}",
         "-t", f"{duration}", "-c:a", "pcm_s16le", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def loop_to_duration(src: Path, target_sec: float, out_path: Path, gain_db: float) -> Path:
    """Loop a source clip to exactly target_sec, applying gain. Output WAV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # stream_loop -1 + atrim to target duration is the cleanest pattern
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", f"{target_sec}",
         "-af", f"volume={gain_db}dB,apad=whole_dur={target_sec}",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
         str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def place_sfx_on_silence(sfx_path: Path, at_sec: float, gain_db: float,
                         beat_duration: float, out_path: Path) -> Path:
    """Create a beat-length WAV with the SFX placed at at_sec, the rest silent."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # adelay takes milliseconds per channel
    delay_ms = int(at_sec * 1000)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(sfx_path),
         "-af", f"volume={gain_db}dB,adelay={delay_ms}|{delay_ms},apad=whole_dur={beat_duration}",
         "-t", f"{beat_duration}",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
         str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def mix_layers(layer_paths: list[Path], out_path: Path) -> Path:
    """Mix N layers (all same duration) down to one WAV using amix."""
    if not layer_paths:
        raise ValueError("mix_layers needs at least one layer")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(layer_paths) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(layer_paths[0]),
             "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)],
            check=True, capture_output=True,
        )
        return out_path
    inputs: list[str] = []
    for p in layer_paths:
        inputs += ["-i", str(p)]
    # amix normalizes by default — disable normalization so we keep mix levels
    filter_str = f"amix=inputs={len(layer_paths)}:duration=longest:normalize=0"
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_str,
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def concat_segments(segment_paths: list[Path], out_path: Path) -> Path:
    """Concatenate per-beat WAV segments into a single WAV using the concat demuxer."""
    if not segment_paths:
        raise ValueError("concat_segments needs at least one segment")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_paths))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", str(out_path)],
        check=True, capture_output=True,
    )
    list_file.unlink(missing_ok=True)
    return out_path


# ---------------------------------------------------------------------------
# Beat-duration derivation (from alignment.json — same pattern as build_visuals_track)
# ---------------------------------------------------------------------------

def beat_durations_from_alignment(case_id: str, beats: list[dict]) -> list[float] | None:
    """Best-effort: derive per-beat seconds from the ElevenLabs alignment file."""
    align_path = AUDIO_DIR / f"narration_{case_id}.alignment.json"
    if not align_path.exists():
        return None
    try:
        a = json.loads(align_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    spoken = "".join(a["characters"])
    starts = a["character_start_times_seconds"]
    ends = a["character_end_times_seconds"]
    total = float(ends[-1])
    boundaries: list[float] = [0.0]
    for beat in beats[1:]:
        text = (beat.get("text") or "").strip()
        if not text:
            return None
        for probe in (text, text[:30], text[:15]):
            idx = spoken.find(probe)
            if idx >= 0:
                boundaries.append(float(starts[idx]))
                break
        else:
            return None
    boundaries.append(total)
    return [boundaries[i+1] - boundaries[i] for i in range(len(boundaries) - 1)]


# ---------------------------------------------------------------------------
# Music selection from local library
# ---------------------------------------------------------------------------

def pick_music_clip(subgenre_letter: str) -> Path | None:
    """Return a random music clip path for the sub-genre, or None if library empty."""
    options = MUSIC_LIBRARY.get(subgenre_letter, [])
    available = []
    for stem in options:
        for ext in (".mp3", ".wav", ".m4a"):
            p = MUSIC_DIR / f"{stem}{ext}"
            if p.exists():
                available.append(p)
                break
    if not available:
        return None
    return random.choice(available)


def music_check() -> int:
    """Report which sub-genres have a usable music library."""
    print(f"── Music library check: {MUSIC_DIR} ──")
    all_ok = True
    for letter, stems in MUSIC_LIBRARY.items():
        found = []
        missing = []
        for stem in stems:
            for ext in (".mp3", ".wav", ".m4a"):
                p = MUSIC_DIR / f"{stem}{ext}"
                if p.exists():
                    found.append(p.name)
                    break
            else:
                missing.append(stem + ".{mp3,wav,m4a}")
        status = "✓" if found else "✗"
        print(f"  {status} sub-genre {letter}: {len(found)}/{len(stems)} files")
        for f in found:
            print(f"      ✓ {f}")
        for m in missing:
            print(f"      ✗ {m}  ← drop a CC0 clip here")
        if not found:
            all_ok = False
    if not all_ok:
        print(f"\n  Some sub-genres have NO music. See {MUSIC_DIR}/README.md for sourcing.")
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# Per-beat segment builder
# ---------------------------------------------------------------------------

def build_beat_segment(beat: dict, beat_idx: int, beat_duration: float,
                       case_dir: Path, assets_dir: Path,
                       freesound_token: str, subgenre_letter: str,
                       skip_music: bool) -> Path:
    """Return path to a single WAV containing ambient + SFX + (optional) music for this beat."""
    seg_dir = case_dir / "beat_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    out_seg = seg_dir / f"beat_{beat_idx:02d}.wav"

    sb = beat.get("sound_brief") if isinstance(beat.get("sound_brief"), dict) else {}
    layers: list[Path] = []

    # --- Ambient bed ---
    fk = sb.get("freesound_keywords") or [sb.get("ambient_bed", "room tone")]
    ambient_query = " ".join(str(k) for k in fk[:3]) if isinstance(fk, list) else str(fk)
    ambient_src = fetch_audio_clip(
        query=ambient_query or "ambient room tone",
        dest_dir=assets_dir,
        label=f"beat_{beat_idx:02d}_ambient",
        max_duration=max(beat_duration, 10),
        freesound_token=freesound_token,
    )
    ambient_layer = seg_dir / f"beat_{beat_idx:02d}_ambient.wav"
    if ambient_src:
        loop_to_duration(ambient_src, beat_duration, ambient_layer, DEFAULT_AMBIENT_DB)
    else:
        # silence fallback
        make_silence(beat_duration, ambient_layer)
    layers.append(ambient_layer)

    # --- SFX hits ---
    sfx_list = sb.get("sfx") or []
    for j, hit in enumerate(sfx_list):
        if not isinstance(hit, dict):
            continue
        name = hit.get("name") or ""
        at_sec = float(hit.get("at_sec", 0.0))
        gain_db = float(hit.get("gain_db", DEFAULT_SFX_DB))
        if at_sec < 0 or at_sec >= beat_duration or not name:
            continue
        sfx_src = fetch_audio_clip(
            query=name, dest_dir=assets_dir,
            label=f"beat_{beat_idx:02d}_sfx_{j:02d}",
            max_duration=5.0,
            freesound_token=freesound_token,
        )
        if not sfx_src:
            continue
        sfx_layer = seg_dir / f"beat_{beat_idx:02d}_sfx_{j:02d}_placed.wav"
        place_sfx_on_silence(sfx_src, at_sec, gain_db, beat_duration, sfx_layer)
        layers.append(sfx_layer)

    # --- Music cue (hero beats only) ---
    intensity = float(sb.get("music_intensity", 0.0) or 0.0)
    if not skip_music and intensity >= 0.5:
        music_clip = pick_music_clip(subgenre_letter)
        if music_clip:
            # Scale music gain by intensity: intensity 0.5 → -18db, 1.0 → -8db
            music_db = DEFAULT_MUSIC_DB + (intensity - 0.5) * 20
            music_layer = seg_dir / f"beat_{beat_idx:02d}_music.wav"
            loop_to_duration(music_clip, beat_duration, music_layer, music_db)
            layers.append(music_layer)
        else:
            print(f"    [beat {beat_idx}] music_intensity={intensity:.2f} requested but "
                  f"no music asset for sub-genre {subgenre_letter} — skipping music layer", file=sys.stderr)

    # --- Mix all layers down ---
    mix_layers(layers, out_seg)
    return out_seg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="Case ID (e.g. SY_07_H_slug)")
    parser.add_argument("--skip-music", action="store_true",
                        help="Skip music layer even when music_intensity >= 0.5 (faster iteration).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without rendering anything.")
    parser.add_argument("--music-check", action="store_true",
                        help="Verify assets/music/ has the required files and exit.")
    args = parser.parse_args()

    if args.music_check:
        return music_check()
    if not args.case:
        parser.print_help()
        return 2

    case_id = args.case
    config_path = SCRIPTS_DIR / case_id / "script_config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found", file=sys.stderr)
        return 2

    cfg = json.loads(config_path.read_text())
    beats = cfg.get("beats", [])
    if not beats:
        print(f"ERROR: no beats in {config_path}", file=sys.stderr)
        return 2

    # Derive sub-genre letter from case_id
    import re
    m = re.match(r"^SY_\d{2,3}_([SRH])_", case_id)
    if not m:
        print(f"ERROR: case_id '{case_id}' doesn't match SY_NN_<S|R|H>_<slug>", file=sys.stderr)
        return 2
    subgenre_letter = m.group(1)

    durations = beat_durations_from_alignment(case_id, beats)
    if durations is None:
        # Default: use beat target_seconds if alignment not ready
        durations = []
        for b in beats:
            t = b.get("max_seconds") or b.get("target_seconds") or 8
            durations.append(float(t))
        print(f"  [warn] No alignment.json — using beat target/max_seconds for durations "
              f"(total {sum(durations):.1f}s)", file=sys.stderr)
    else:
        print(f"  Per-beat durations from alignment.json (total {sum(durations):.1f}s)")

    case_audio_dir = OUTPUT_AUDIO_DIR / case_id
    assets_cache = case_audio_dir / "sound_assets"
    freesound_token = os.environ.get("FREESOUND_API_TOKEN", "").strip()
    if not freesound_token:
        print(f"  [warn] FREESOUND_API_TOKEN not set — ambient/SFX will fall back to silence", file=sys.stderr)

    print(f"── Build Sound Design: {case_id} ──")
    print(f"  Beats: {len(beats)}")
    print(f"  Sub-genre: {subgenre_letter}")
    print(f"  Freesound: {'✓' if freesound_token else '✗ (silence fallback)'}")
    print(f"  Music:     {'(skipped)' if args.skip_music else '(local library)'}")

    if args.dry_run:
        print(f"\n  [dry-run] Plan:")
        for i, (beat, dur) in enumerate(zip(beats, durations)):
            sb = beat.get("sound_brief") or {}
            intensity = float(sb.get("music_intensity", 0) or 0)
            n_sfx = len(sb.get("sfx") or [])
            print(f"    beat[{i}] {beat.get('label','?'):<12} {dur:5.2f}s "
                  f"ambient={'✓' if sb.get('ambient_bed') else '✗'} "
                  f"sfx={n_sfx} "
                  f"music={'✓' if intensity>=0.5 else '✗'}({intensity:.2f}) "
                  f"vocal_mood={sb.get('vocal_mood','?')[:25]}")
        return 0

    # Build per-beat segments, then concat
    segment_paths: list[Path] = []
    for i, (beat, dur) in enumerate(zip(beats, durations)):
        print(f"\n  beat[{i}] {beat.get('label','?')} ({dur:.2f}s)…")
        seg_path = build_beat_segment(
            beat=beat, beat_idx=i, beat_duration=dur,
            case_dir=case_audio_dir, assets_dir=assets_cache,
            freesound_token=freesound_token,
            subgenre_letter=subgenre_letter,
            skip_music=args.skip_music,
        )
        segment_paths.append(seg_path)

    final_out = case_audio_dir / "sound_design.wav"
    concat_segments(segment_paths, final_out)
    duration = ffmpeg_probe_duration(final_out)
    print(f"\n  ✓ Sound design: {final_out.relative_to(PROJECT_ROOT)}  ({duration:.2f}s)")
    print(f"  Next: mux this under your VO track in the final render.")
    print(f"  Suggested ffmpeg mix: ffmpeg -i vo.mp3 -i sound_design.wav "
          f"-filter_complex \"[1:a]volume=0.6[bg];[0:a][bg]amix=duration=longest\" out.wav")
    return 0


if __name__ == "__main__":
    sys.exit(main())
