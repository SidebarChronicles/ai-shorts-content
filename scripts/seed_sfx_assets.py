#!/usr/bin/env python3
"""Seed assets/sfx/ with ~45 procedurally-synthesized SFX across per-vertical folders.

Why procedural instead of Pixabay/Freesound URLs:
- 100% reliable (no broken hotlinks, no auth)
- Effectively public-domain (algorithmic, not copyrighted)
- We control exact tonal characteristics per vertical

Categories (FFmpeg synthesis recipes):
  whoosh — pink/white noise + bandpass sweep + envelope (transitional)
  sting  — sine + FM + short envelope (punctuation, attention grab)
  riser  — sine sweep ascending + filter sweep + build (tension)
  drop   — sine sweep descending + lowpass + heavy envelope (impact)
  atmos  — low sine + LFO + delays (ambient, sustained tension)

Generates ~45 files across 11 vertical subfolders:
  _shared/        — basic neutral whooshes/stings (fallback)
  story_survival/ — tense whooshes, drops, alarms
  story_horror/   — risers, atmospheric drones, jump stings
  story_reddit/   — light whooshes, record-scratch-adjacent, neutral
  games/          — action whooshes, glitch, impact
  movies/         — cinematic whooshes, trailer risers, bass drops
  mythology/      — epic risers, mystical chimes, deep stings
  mysteries/      — tension atmos, clue stings, subtle whooshes
  cases/          — same as mysteries (shared template)
  topx/           — bright whooshes, counter stings, reveal drops
  finance/        — clean whooshes, neutral chimes

Usage:
    python scripts/seed_sfx_assets.py              # idempotent — skips existing
    python scripts/seed_sfx_assets.py --force      # regenerate everything
    python scripts/seed_sfx_assets.py --only games # rebuild one vertical
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SFX_ROOT = PROJECT_ROOT / "assets" / "sfx"


def _run(cmd: list[str], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        sys.exit(f"ERROR generating {target}:\n{result.stderr[-400:]}")


# ---------------------------------------------------------------------------
# Synthesis primitives
# ---------------------------------------------------------------------------

def gen_whoosh(vertical: str, name: str, low_freq: float, high_freq: float,
               duration: float = 0.4, color: str = "pink",
               amplitude: float = 0.5, brightness: float = 1.0,
               force: bool = False) -> bool:
    """Filtered-noise whoosh — bandpass sweep + envelope.

    color: 'pink' (warm) | 'white' (bright/sharp) | 'brown' (deep/heavy)
    brightness: post-filter boost on high freqs (0.5 = muffled, 1.5 = piercing)
    """
    out = SFX_ROOT / vertical / f"{name}.wav"
    if out.exists() and not force:
        return False
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"anoisesrc=color={color}:amplitude={amplitude}",
        "-af",
        (f"highpass=f={low_freq},lowpass=f={high_freq * brightness},"
         f"afade=t=in:d=0.05,afade=t=out:d=0.12:st={duration-0.12:.2f},"
         f"volume=0.7"),
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    return True


def gen_sting(vertical: str, name: str, freq: float, duration: float = 0.2,
              wave: str = "sine", harmonics: int = 1, fade_out: float = 0.1,
              force: bool = False) -> bool:
    """Tonal sting — sine (optionally with harmonics) + short envelope.

    harmonics: 1=pure tone, 2-3=richer (adds octave/fifth)
    """
    out = SFX_ROOT / vertical / f"{name}.wav"
    if out.exists() and not force:
        return False
    inputs = ["-f", "lavfi", "-t", f"{duration:.2f}",
              "-i", f"{wave}=frequency={freq}:sample_rate=44100"]
    mix_labels = ["[0:a]"]
    if harmonics >= 2:
        inputs += ["-f", "lavfi", "-t", f"{duration:.2f}",
                   "-i", f"{wave}=frequency={freq * 2}:sample_rate=44100"]
        mix_labels.append("[1:a]")
    if harmonics >= 3:
        inputs += ["-f", "lavfi", "-t", f"{duration:.2f}",
                   "-i", f"{wave}=frequency={freq * 1.5}:sample_rate=44100"]
        mix_labels.append("[2:a]")

    filter_complex = (
        "".join(mix_labels)
        + f"amix=inputs={harmonics}:duration=longest:normalize=0,"
        + f"afade=t=in:d=0.005,afade=t=out:d={fade_out}:st={duration-fade_out:.3f},"
        + "volume=0.55[out]"
    )
    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", filter_complex, "-map", "[out]",
           "-c:a", "pcm_s16le", "-ar", "44100",
           str(out)]
    _run(cmd, out)
    return True


def gen_riser(vertical: str, name: str, start_freq: float = 150,
              end_freq: float = 1200, duration: float = 1.5,
              force: bool = False) -> bool:
    """Ascending tension riser — sine glissando + noise + envelope build."""
    out = SFX_ROOT / vertical / f"{name}.wav"
    if out.exists() and not force:
        return False
    cmd = [
        "ffmpeg", "-y",
        # Sine that ramps in frequency via the formula `t*delta + start`
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", (f"sine=frequency={start_freq}:sample_rate=44100"),
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", "anoisesrc=color=pink:amplitude=0.3",
        "-filter_complex",
        (f"[0:a]asetrate=44100*1.0,"
         # Apply a low-to-high bandpass sweep on the noise
         f"volume=0.45[tone];"
         f"[1:a]highpass=f={start_freq * 0.7},lowpass=f={end_freq * 1.2},"
         f"volume=0.35[noise];"
         f"[tone][noise]amix=inputs=2:duration=longest:normalize=0,"
         f"afade=t=in:d=0.1,afade=t=out:d=0.15:st={duration-0.15:.2f},"
         f"volume=0.6[out]"),
        "-map", "[out]",
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    return True


def gen_drop(vertical: str, name: str, start_freq: float = 800,
             end_freq: float = 60, duration: float = 1.0,
             force: bool = False) -> bool:
    """Descending impact drop — high-to-low sine + sub-bass + heavy envelope."""
    out = SFX_ROOT / vertical / f"{name}.wav"
    if out.exists() and not force:
        return False
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"sine=frequency={start_freq}:sample_rate=44100",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"sine=frequency={end_freq}:sample_rate=44100",
        "-filter_complex",
        (f"[0:a]volume=0.4,afade=t=out:d={duration*0.6:.2f}:st={duration*0.2:.2f}[high];"
         f"[1:a]volume=0.7,afade=t=in:d={duration*0.3:.2f}[low];"
         f"[high][low]amix=inputs=2:duration=longest:normalize=0,"
         f"afade=t=in:d=0.02,afade=t=out:d=0.2:st={duration-0.2:.2f},"
         f"volume=0.6[out]"),
        "-map", "[out]",
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    return True


def gen_atmos(vertical: str, name: str, base_freq: float = 80,
              duration: float = 4.0, force: bool = False) -> bool:
    """Ambient atmospheric drone — low sine + slow LFO + tremolo."""
    out = SFX_ROOT / vertical / f"{name}.wav"
    if out.exists() and not force:
        return False
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"sine=frequency={base_freq}:sample_rate=44100",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"sine=frequency={base_freq * 1.5}:sample_rate=44100",
        "-filter_complex",
        (f"[0:a]volume=0.45[low];"
         f"[1:a]volume=0.3,tremolo=f=0.6:d=0.3[high];"
         f"[low][high]amix=inputs=2:duration=longest:normalize=0,"
         f"lowpass=f=600,"
         f"afade=t=in:d=0.5,afade=t=out:d=0.8:st={duration-0.8:.2f},"
         f"volume=0.5[out]"),
        "-map", "[out]",
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    return True


# ---------------------------------------------------------------------------
# Per-vertical recipes
# ---------------------------------------------------------------------------

# Each vertical gets 4-5 SFX. Format: list of (gen_fn, kwargs)
RECIPES: dict[str, list[tuple]] = {
    # Fallback — neutral basics
    "_shared": [
        (gen_whoosh, dict(name="whoosh_basic_01", low_freq=300, high_freq=2200, duration=0.4)),
        (gen_whoosh, dict(name="whoosh_basic_02", low_freq=200, high_freq=1500, duration=0.35)),
        (gen_whoosh, dict(name="whoosh_basic_03", low_freq=400, high_freq=2800, duration=0.45, color="white")),
        (gen_sting,  dict(name="sting_neutral_01", freq=880, duration=0.18)),
        (gen_sting,  dict(name="sting_neutral_02", freq=660, duration=0.20, harmonics=2)),
    ],

    # Survival — tense whooshes + heavy drops
    "story_survival": [
        (gen_whoosh, dict(name="whoosh_tense_01", low_freq=180, high_freq=1400, duration=0.5, color="pink", brightness=0.9)),
        (gen_whoosh, dict(name="whoosh_tense_02", low_freq=250, high_freq=1800, duration=0.4, color="pink")),
        (gen_drop,   dict(name="drop_heavy_01", start_freq=600, end_freq=50, duration=0.9)),
        (gen_sting,  dict(name="sting_alarm_01", freq=440, duration=0.25, harmonics=3)),
    ],

    # Horror — risers + atmos + jump stings
    "story_horror": [
        (gen_riser,  dict(name="riser_dread_01", start_freq=100, end_freq=900, duration=1.8)),
        (gen_riser,  dict(name="riser_dread_02", start_freq=80, end_freq=600, duration=2.2)),
        (gen_atmos,  dict(name="atmos_drone_01", base_freq=65, duration=4.0)),
        (gen_atmos,  dict(name="atmos_drone_02", base_freq=90, duration=3.5)),
        (gen_sting,  dict(name="sting_jump_01", freq=1320, duration=0.15, harmonics=3, fade_out=0.13)),
    ],

    # Reddit — light, page-turn-ish, neutral
    "story_reddit": [
        (gen_whoosh, dict(name="whoosh_page_01", low_freq=600, high_freq=3200, duration=0.3, color="white", brightness=1.2)),
        (gen_whoosh, dict(name="whoosh_page_02", low_freq=500, high_freq=2800, duration=0.35, color="white")),
        (gen_sting,  dict(name="sting_record_01", freq=550, duration=0.22, harmonics=2)),
        (gen_sting,  dict(name="sting_neutral_03", freq=730, duration=0.18)),
    ],

    # Games — action whooshes + glitchy stings
    "games": [
        (gen_whoosh, dict(name="whoosh_action_01", low_freq=250, high_freq=2400, duration=0.35, color="white", brightness=1.3)),
        (gen_whoosh, dict(name="whoosh_action_02", low_freq=300, high_freq=2600, duration=0.3)),
        (gen_sting,  dict(name="sting_glitch_01", freq=1100, duration=0.12, harmonics=3, fade_out=0.1)),
        (gen_drop,   dict(name="drop_impact_01", start_freq=900, end_freq=80, duration=0.7)),
    ],

    # Movies — cinematic whooshes + bass drops
    "movies": [
        (gen_whoosh, dict(name="whoosh_cinematic_01", low_freq=150, high_freq=1800, duration=0.6, color="brown", brightness=0.85)),
        (gen_riser,  dict(name="riser_trailer_01", start_freq=80, end_freq=800, duration=2.0)),
        (gen_drop,   dict(name="drop_bass_01", start_freq=400, end_freq=40, duration=1.2)),
        (gen_sting,  dict(name="sting_cinema_01", freq=220, duration=0.3, harmonics=2)),
    ],

    # Mythology — epic risers + mystical chimes
    "mythology": [
        (gen_riser,  dict(name="riser_epic_01", start_freq=120, end_freq=1000, duration=2.0)),
        (gen_atmos,  dict(name="atmos_mystical_01", base_freq=110, duration=4.0)),
        (gen_sting,  dict(name="sting_chime_01", freq=1320, duration=0.4, harmonics=3, fade_out=0.35)),
        (gen_sting,  dict(name="sting_chime_02", freq=988, duration=0.45, harmonics=2, fade_out=0.4)),
    ],

    # Mysteries — tension atmos + clue stings
    "mysteries": [
        (gen_atmos,  dict(name="atmos_tension_01", base_freq=70, duration=4.5)),
        (gen_atmos,  dict(name="atmos_tension_02", base_freq=95, duration=3.8)),
        (gen_sting,  dict(name="sting_clue_01", freq=440, duration=0.25, harmonics=2)),
        (gen_whoosh, dict(name="whoosh_subtle_01", low_freq=180, high_freq=1200, duration=0.5, color="pink", brightness=0.8)),
    ],

    # Cases — shares mysteries template (similar mood)
    "cases": [
        (gen_atmos,  dict(name="atmos_tension_01", base_freq=70, duration=4.5)),
        (gen_sting,  dict(name="sting_clue_01", freq=440, duration=0.25, harmonics=2)),
        (gen_sting,  dict(name="sting_clue_02", freq=370, duration=0.28, harmonics=3)),
        (gen_whoosh, dict(name="whoosh_subtle_01", low_freq=180, high_freq=1200, duration=0.5, color="pink", brightness=0.8)),
    ],

    # Top X — bright whooshes + counter stings + reveal drops
    "topx": [
        (gen_whoosh, dict(name="whoosh_bright_01", low_freq=400, high_freq=3200, duration=0.3, color="white", brightness=1.3)),
        (gen_whoosh, dict(name="whoosh_bright_02", low_freq=500, high_freq=3000, duration=0.35, color="white")),
        (gen_sting,  dict(name="sting_counter_01", freq=880, duration=0.15, harmonics=2)),
        (gen_drop,   dict(name="drop_reveal_01", start_freq=700, end_freq=70, duration=0.8)),
    ],

    # Finance — clean, minimal, neutral
    "finance": [
        (gen_whoosh, dict(name="whoosh_clean_01", low_freq=350, high_freq=2500, duration=0.3, color="white", brightness=1.0)),
        (gen_sting,  dict(name="sting_chime_clean_01", freq=1100, duration=0.3, harmonics=2, fade_out=0.25)),
        (gen_sting,  dict(name="sting_chime_clean_02", freq=880, duration=0.35, harmonics=2, fade_out=0.3)),
    ],
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerate even if files exist")
    parser.add_argument("--only", default=None, help="Only seed one vertical (e.g. games)")
    args = parser.parse_args()

    if args.force:
        # Wipe all .wav under assets/sfx/ (preserves any custom additions in non-WAV formats)
        for f in SFX_ROOT.rglob("*.wav"):
            f.unlink()
            print(f"  removed: {f.relative_to(PROJECT_ROOT)}")

    n_generated = 0
    n_skipped = 0
    for vertical, recipes in RECIPES.items():
        if args.only and vertical != args.only:
            continue
        print(f"── {vertical} ──")
        for gen_fn, kwargs in recipes:
            kwargs_full = {"vertical": vertical, "force": args.force, **kwargs}
            generated = gen_fn(**kwargs_full)
            name = kwargs["name"]
            if generated:
                print(f"  ✓ {vertical}/{name}.wav")
                n_generated += 1
            else:
                print(f"  · exists: {vertical}/{name}.wav  (use --force to regen)")
                n_skipped += 1

    print(f"\n✓ Done. {n_generated} generated, {n_skipped} skipped (already existed).")
    if n_generated == 0 and not args.force:
        print("  All files already exist. Pass --force to regenerate.")


if __name__ == "__main__":
    main()
