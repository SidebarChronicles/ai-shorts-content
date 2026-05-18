#!/usr/bin/env python3
"""Story sub-genre script templates and config scaffolding.

The actual narrative writing is done by Claude during the routine fire
(STEP 3 of daily-shorts-pipeline/SKILL.md). This module provides the
deterministic scaffolding: hook templates, voice assignments, visual
style hints, and the 7-beat structure each sub-genre must follow.

The routine workflow per story video:
  1. Read SY_NN_<sub>_<slug>.md from story_queue/ for premise + hook angle
  2. Call get_template(subgenre) here for the canonical scaffold
  3. Claude writes the 7 beat texts following the template's rules
  4. Write output/scripts/SY_NN_*/script_config.json with the populated beats
  5. check_script_structure.py lints the result before audio generation

Usage (CLI — scaffolds a starter config to be filled in by Claude):
    python scripts/story_script_writer.py --case SY_01_S_caveexplorer

The script writes `output/scripts/<case>/script_config.json` with empty
beat text fields that Claude fills in during the routine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_json  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

QUEUE_DIR = PROJECT_ROOT / "story_queue"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

# Voice IDs from VOICE_LIBRARY in make_audio_elevenlabs.py
VOICE_IDS = {
    "Charlie": "IKne3meq5aSn9XLyUdCD",
    "Brian":   "nPczCjzI2devNBz1zQrb",
    "Daniel":  "onwK4e9ZLuTAKqWW03F9",
    "Rachel":  "21m00Tcm4TlvDq8ikWAM",
    "Bella":   "EXAVITQu4vr4xnSDxMaL",
    "Domi":    "AZnzlk1XvdvUeBnXmlld",
    "Elli":    "MF3mGyEYCl7XYWbV9V6O",
    "Nicole":  "piTKgcLEGmPE4e6mEKli",
}

# Per-sub-genre voice menu by protagonist gender. The DEFAULT (first entry)
# applies when the queue doesn't specify. Writer/queueing-human can override
# in two ways:
#   1) Queue file: add "Voice: <name>" line to override per video
#   2) script_config.json: set voice_id directly (post-scaffold edit)
#
# Pick by POV gender first, then by tone match. Rule of thumb:
#   - First-person female narrator → use a female voice. Always.
#   - First-person male narrator   → use a male voice. Always.
#   - Third-person/omniscient      → use the sub-genre's default tone voice.
VOICE_MENU = {
    "survival": {
        "M": ["Charlie", "Adam", "Callum"],
        "F": ["Domi",    "Rachel", "Elli"],
    },
    "reddit": {
        "M": ["Brian",  "Charlie", "Daniel"],
        "F": ["Rachel", "Domi",    "Elli"],
    },
    "horror": {
        "M": ["Daniel", "Brian",  "Adam"],
        "F": ["Nicole", "Bella",  "Rachel"],
    },
}


# ---------------------------------------------------------------------------
# Sub-genre templates
# ---------------------------------------------------------------------------

# Default exclude list seeded into every visual_brief to suppress the Pokemon-bug
# class of hallucinations (yellow creatures, cartoon faces, etc.) even when the
# writer forgets to add anything sub-genre-specific.
BASELINE_VISUAL_EXCLUDE = [
    "people", "creatures", "faces", "characters", "anime", "cartoon",
    "logos", "text overlays", "watermarks", "yellow mascot", "fantasy creature",
]

SURVIVAL_TEMPLATE = {
    "subgenre": "survival",
    "subgenre_letter": "S",
    "voice_name": "Charlie",
    "voice_id": VOICE_IDS["Charlie"],
    "voice_speed": 0.95,
    "model_id": "eleven_turbo_v2",
    "color_grade_vertical": "story",
    "hook_formula": "violation_first",
    "hook_template": "[Threat/violation in 4-5 words]. [Context after.] (TikTok-first: lead with the shock.)",
    "hook_example_good": "Footprints. Inside my cabin. While I slept.",
    "hook_example_bad":  "Day 1 of being snowed in. I'm not alone out here. ← buries the violation",
    "visual_brief_defaults": {
        "mood": "tense, isolated, weathered",
        "lighting": "harsh natural daylight or single firelight, hard shadows",
        "color": "muted earth tones, desaturated, cold highlights",
        "exclude": BASELINE_VISUAL_EXCLUDE,
    },
    "sound_brief_defaults": {
        "ambient_bed": "wind through trees or open space, distant water drip, cold air room tone -22db",
        "music_intensity": 0.3,
        "vocal_mood": "controlled tension, measured pace, breath audible on reveals",
        "mix_note": "ambient -18db under VO, SFX hits duck VO -3db, hero-beat music sidechained to VO",
    },
    "anti_patterns": [
        "Hey guys", "What's up", "Today we're", "So I", "Imagine if",
        "Day N of [scenario]. Today I [escalation] ← deprecated May 18 2026 (front-loads setup, not violation)",
        "starting with 'The' / 'A' / 'An' / 'In'",
        "setting-first openers ('In a remote cabin...', 'On Day 1...') — lead with action or subject",
        "build-up structure [setup→reveal] — flip it to [reveal→setup]",
    ],
    "beats": [
        {"label": "hook", "purpose": "Hit Day N + escalation in ≤12 words", "target_seconds": 0, "max_seconds": 2.5, "visual_style": "wide establishing shot, urgency"},
        {"label": "setup", "purpose": "Frame what's happening at this moment", "target_seconds": 3, "max_seconds": 12, "visual_style": "subject mid-action, environmental context"},
        {"label": "build", "purpose": "Add stakes — what makes today different", "target_seconds": 15, "max_seconds": 13, "visual_style": "tension shot, dutch angle, close detail"},
        {"label": "mid_anchor", "purpose": "Discovery, threat reveal, or escalation moment", "target_seconds": 28, "max_seconds": 5, "visual_style": "HERO SHOT — Pika clip preferred, dramatic reveal"},
        {"label": "expand", "purpose": "What does this mean for tomorrow / survival", "target_seconds": 33, "max_seconds": 12, "visual_style": "subject reaction, planning, gear close-up"},
        {"label": "payoff", "purpose": "Resolution beat OR cliffhanger for Day N+1", "target_seconds": 45, "max_seconds": 10, "visual_style": "wide environmental shot, change of light"},
        {"label": "cta", "purpose": "FOLLOW-DRIVER (v2): 'Day N+1 drops tomorrow — follow so you don't miss it.' Drives follower growth (Creator Rewards + YPP unlock)", "target_seconds": 55, "max_seconds": 5, "visual_style": "fade-to-loop frame, same composition as hook"},
    ],
    "character_continuity_prompt": (
        "[Same protagonist across episodes. Default description: tall man late 30s, "
        "weathered face, dark hair, faded blue jacket, dirt-smudged. Include in every "
        "Flux prompt to maintain visual continuity. Override per-character in the "
        "queue entry's 'Protagonist:' field.]"
    ),
    "visual_palette": "muted earth tones, high contrast, slightly desaturated, single light source",
}


REDDIT_TEMPLATE = {
    "subgenre": "reddit",
    "subgenre_letter": "R",
    "voice_name": "Brian",
    "voice_id": VOICE_IDS["Brian"],
    "voice_speed": 0.92,
    "model_id": "eleven_multilingual_v2",
    "color_grade_vertical": "story",
    "hook_formula": "violation_then_question",
    "hook_template": "My [relation] [outrageous action in 5 words]. AITA? (Lead with violation; AITA comes last.)",
    "hook_example_good": "My neighbor destroyed my daughter's garden. So I fenced him out. AITA?",
    "hook_example_bad":  "AITA for putting up a fence after my neighbor mowed my lawn? ← question-first, viewer waits",
    "visual_brief_defaults": {
        "mood": "confiding, slightly indignant, naturalistic",
        "lighting": "warm interior practicals, soft window light, naturalistic",
        "color": "warm domestic tones, contemporary, mid-saturation",
        "exclude": BASELINE_VISUAL_EXCLUDE + ["fantasy", "horror", "supernatural", "celebrities"],
    },
    "sound_brief_defaults": {
        "ambient_bed": "household ambience, distant traffic, fridge hum, low room tone -24db",
        "music_intensity": 0.2,
        "vocal_mood": "confiding narrator, slight indignation, conversational pace",
        "mix_note": "ambient -22db under VO, no SFX unless emotional pivot, music swells on the verdict reveal only",
    },
    "anti_patterns": [
        "So I'm posting", "Hey Reddit", "Long time lurker", "Strap in",
        "verbatim Reddit quote — paraphrase ALWAYS",
        "AITA-as-first-sentence — flip to violation-first, question last",
        "starting with 'The' / 'A' / 'An' / 'In' — too soft for sentence 1",
    ],
    "beats": [
        {"label": "hook", "purpose": "AITA question + the outrage in ≤12 words", "target_seconds": 0, "max_seconds": 2.5, "visual_style": "character expression close-up, eye contact"},
        {"label": "setup", "purpose": "Who the people are + the relationship", "target_seconds": 3, "max_seconds": 12, "visual_style": "two-shot or environmental setup"},
        {"label": "build", "purpose": "What led up to the incident", "target_seconds": 15, "max_seconds": 13, "visual_style": "scene reconstruction, naturalistic"},
        {"label": "mid_anchor", "purpose": "The twist or escalation that flips audience loyalty", "target_seconds": 28, "max_seconds": 5, "visual_style": "HERO SHOT — reaction face, the moment everything changes"},
        {"label": "expand", "purpose": "The fallout / consequences", "target_seconds": 33, "max_seconds": 12, "visual_style": "aftermath shots, body language"},
        {"label": "payoff", "purpose": "What I did about it / what the other person did", "target_seconds": 45, "max_seconds": 10, "visual_style": "resolution scene, lighting shift"},
        {"label": "cta", "purpose": "FOLLOW-DRIVER (v2): 'AITA? Comment your verdict. Follow for daily AITAs.' Drives follows + comments (algorithm + monetization)", "target_seconds": 55, "max_seconds": 5, "visual_style": "freeze-frame on protagonist, looking at camera"},
    ],
    "character_continuity_prompt": (
        "[Characters rotate per video; no cross-video continuity needed. "
        "Use generic, anonymized physical descriptions in Flux prompts — "
        "do not invoke real Reddit usernames or specific story details.]"
    ),
    "anti_plagiarism_rule": (
        "Reddit posts ARE copyrighted by their authors. The script must REWRITE "
        "the story in original prose: different word choices, restructured narrative, "
        "anonymized names + locations, paraphrased dialogue. Use the source Reddit "
        "post as inspiration only. Verbatim reproduction risks YouTube strike."
    ),
    "visual_palette": "warm domestic tones, naturalistic lighting, contemporary setting",
}


HORROR_TEMPLATE = {
    "subgenre": "horror",
    "subgenre_letter": "H",
    "voice_name": "Daniel",
    "voice_id": VOICE_IDS["Daniel"],
    "voice_speed": 0.88,
    "model_id": "eleven_multilingual_v2",
    "color_grade_vertical": "story",
    "hook_formula": "wrong_detail_first",
    "hook_template": "[Wrong detail in 4-5 words]. [Mundane context after.] (Lead with the wrongness.)",
    "hook_example_good": "The lock is on the wrong side. From the basement, you can't get out.",
    "hook_example_bad":  "The basement door has a lock. The lock is on the wrong side. ← buries the wrongness",
    "visual_brief_defaults": {
        "mood": "dread, claustrophobic, silence-dominant",
        "lighting": "single warm light source against deep shadow, dark frame negative space",
        "color": "near-monochrome, blue-black shadows, single warm highlight, high contrast",
        "exclude": BASELINE_VISUAL_EXCLUDE + ["bright sunlight", "color saturation", "smiling subjects", "wide-eyed shock cliché"],
    },
    "sound_brief_defaults": {
        "ambient_bed": "room tone, low hum, silence-dominant, refrigerator pulse -28db (let silence speak)",
        "music_intensity": 0.25,
        "vocal_mood": "tight whisper, slow tempo, breath audible on the reveal",
        "mix_note": "ambient very low so silence reads as silence, hero-beat music spikes to 0.7 then drops to 0 on reveal, SFX hit on the wrong-detail mention",
    },
    "anti_patterns": [
        "Let me tell you", "There was once", "I'll never forget", "Years ago",
        "fan-fiction of existing IP (Slenderman, SCP, etc) — original creepypasta ONLY",
        "[mundane setup → wrong detail] structure — flip to [wrong detail → setup]",
        "starting with 'The' / 'A' / 'An' / 'In' — soft and slow for sentence 1",
    ],
    "beats": [
        {"label": "hook", "purpose": "Setup → wrong detail. The wrong detail IS the hook.", "target_seconds": 0, "max_seconds": 2.5, "visual_style": "static frame, single subject, deep shadow"},
        {"label": "setup", "purpose": "Ground the listener in normality before the realization", "target_seconds": 3, "max_seconds": 12, "visual_style": "innocuous environment, slow push-in"},
        {"label": "build", "purpose": "Second wrong thing, third wrong thing, escalating", "target_seconds": 15, "max_seconds": 13, "visual_style": "tighter framing, lower light, off-center subject"},
        {"label": "mid_anchor", "purpose": "Realization — the wrongness is intentional, not coincidence", "target_seconds": 28, "max_seconds": 5, "visual_style": "HERO SHOT — first proper look at the threat, partial reveal"},
        {"label": "expand", "purpose": "Protagonist's reaction / failed escape", "target_seconds": 33, "max_seconds": 12, "visual_style": "POV unsteady, breath sound, oppressive shadows"},
        {"label": "payoff", "purpose": "Final confrontation or surrender", "target_seconds": 45, "max_seconds": 10, "visual_style": "single decisive composition, threat now fully visible"},
        {"label": "cta", "purpose": "FOLLOW-DRIVER (v2): 'Don't [verb] [object]. Follow if you want more.' Warning hook + follow ask in one line", "target_seconds": 55, "max_seconds": 5, "visual_style": "match-cut to the hook composition (loop trigger)"},
    ],
    "character_continuity_prompt": (
        "[First-person POV by default. The 'protagonist' is the camera. Brief "
        "external glimpses (hands, reflections) are allowed but no full-body shots "
        "of the narrator. The THREAT may be partially revealed in mid_anchor and "
        "fully shown in payoff — keep its visual design consistent within a video.]"
    ),
    "original_only_rule": (
        "NO adapting existing creepypasta IP (Slenderman, SCP, Backrooms, "
        "Mr. Wisepuff, etc). Every horror story must be Claude's original micro-"
        "fiction. The premise can borrow tropes (haunted house, doppelganger, "
        "deep-sea creature, etc) but the specific entity, setting, and prose "
        "must be new."
    ),
    "visual_palette": "near-monochrome, blue-black shadows, single warm light source, high contrast",
}


TEMPLATES = {
    "S": SURVIVAL_TEMPLATE,
    "R": REDDIT_TEMPLATE,
    "H": HORROR_TEMPLATE,
    "survival": SURVIVAL_TEMPLATE,
    "reddit": REDDIT_TEMPLATE,
    "horror": HORROR_TEMPLATE,
}


def get_template(subgenre: str) -> dict:
    """Return the template dict for a sub-genre letter or full name."""
    t = TEMPLATES.get(subgenre)
    if not t:
        sys.exit(f"ERROR: unknown sub-genre '{subgenre}'. Valid: S/R/H or survival/reddit/horror")
    return t


def extract_subgenre_letter(case_id: str) -> str:
    """SY_01_S_caveexplorer → 'S'"""
    m = re.match(r"^SY_\d{2,3}_([SRH])_", case_id)
    if not m:
        sys.exit(f"ERROR: case_id '{case_id}' doesn't match SY_NN_<S|R|H>_<slug>")
    return m.group(1)


def read_queue_overrides(case_id: str) -> dict:
    """Pull voice + narrator-gender overrides from the queue file if present.

    Looks for these patterns in story_queue/<case_id>.md:
      **Voice:** <name>           → exact voice override (Rachel, Daniel, etc.)
      **Narrator gender:** F      → picks default voice for sub-genre + gender

    Voice override (if a valid library name) takes precedence over gender.
    """
    queue_file = QUEUE_DIR / f"{case_id}.md"
    overrides: dict = {}
    if not queue_file.exists():
        return overrides
    text = queue_file.read_text()
    voice_m = re.search(r"\*\*Voice:\*\*\s*([A-Za-z]+)", text)
    gender_m = re.search(r"\*\*Narrator gender:\*\*\s*([MFmf])", text)
    if voice_m:
        name = voice_m.group(1).strip()
        if name in VOICE_IDS:
            overrides["voice_name"] = name
            overrides["voice_id"] = VOICE_IDS[name]
    if gender_m:
        overrides["narrator_gender"] = gender_m.group(1).upper()
    return overrides


def scaffold_script_config(case_id: str, out_path: Path | None = None) -> Path:
    """Write a starter script_config.json with empty beat texts the routine will fill in.

    Pre-populates: voice, model, speed, color grade, beat labels + purpose hints.
    Voice can be overridden in the queue file via "**Voice:** <name>" or
    "**Narrator gender:** M|F" — see VOICE_MENU for per-sub-genre options.
    Leaves: hook_text, beat texts, title, keywords (Claude fills these in).
    """
    letter = extract_subgenre_letter(case_id)
    template = get_template(letter)
    overrides = read_queue_overrides(case_id)

    case_dir = SCRIPTS_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        out_path = case_dir / "script_config.json"

    # Resolve voice: explicit Voice: override > gender-default from VOICE_MENU > template default
    voice_name = template["voice_name"]
    voice_id = template["voice_id"]
    if "voice_name" in overrides:
        voice_name = overrides["voice_name"]
        voice_id = overrides["voice_id"]
    elif "narrator_gender" in overrides:
        gender = overrides["narrator_gender"]
        menu = VOICE_MENU.get(template["subgenre"], {}).get(gender, [])
        if menu:
            voice_name = menu[0]
            voice_id = VOICE_IDS[voice_name]

    vb_defaults = template.get("visual_brief_defaults", {})
    sb_defaults = template.get("sound_brief_defaults", {})

    config = {
        "_doc": (
            f"AI Story script ({template['subgenre']}). "
            f"This file scaffolds the 7-beat structure. The daily-shorts-pipeline "
            f"routine fills in 'text', 'keywords', 'title', 'description', "
            f"'visual_brief' and 'sound_brief' fields at production time, then runs "
            f"check_script_structure.py to lint, then make_audio_elevenlabs.py + "
            f"build_visuals_track.py + build_sound_design.py."
        ),
        "case_id": case_id,
        "vertical": "story",
        "subgenre": template["subgenre"],
        "voice_id": voice_id,
        "voice_name": voice_name,
        "voice_speed": template["voice_speed"],
        "model_id": template["model_id"],
        "color_grade_vertical": template["color_grade_vertical"],
        "hook_formula": template["hook_formula"],
        "hook_template": template["hook_template"],
        "hook_anti_patterns": template["anti_patterns"],
        "character_continuity_hint": template["character_continuity_prompt"],
        "visual_palette": template["visual_palette"],
        "visual_brief_defaults": vb_defaults,
        "sound_brief_defaults": sb_defaults,
        "title": "[FILL IN]",
        "description_lead": "[FILL IN — 1-2 sentence story summary, no spoilers]",
        "beats": [
            {
                "label": b["label"],
                "text": "[FILL IN]",
                "keywords": [],
                "purpose_hint": b["purpose"],
                "target_seconds": b["target_seconds"],
                "max_seconds": b["max_seconds"],
                "visual_style_hint": b["visual_style"],
                "visual_brief": {
                    "_FILL_IN": True,
                    "mood": vb_defaults.get("mood", "[fill in]"),
                    "subject": "[fill in — concrete noun phrase, what the camera shows]",
                    "framing": "[fill in — e.g. medium close-up, eye-level, centered]",
                    "lens": "[fill in — e.g. 35mm, shallow DOF]",
                    "lighting": vb_defaults.get("lighting", "[fill in]"),
                    "color": vb_defaults.get("color", "[fill in]"),
                    "props": [],
                    "exclude": list(vb_defaults.get("exclude", BASELINE_VISUAL_EXCLUDE)),
                    "stock_keywords": [],
                },
                "sound_brief": {
                    "_FILL_IN": True,
                    "ambient_bed": sb_defaults.get("ambient_bed", "[fill in]"),
                    "sfx": [],
                    "music_cue": "[fill in — natural-language description; empty string = no music for this beat]",
                    "music_intensity": sb_defaults.get("music_intensity", 0.3),
                    "vocal_mood": sb_defaults.get("vocal_mood", "[fill in]"),
                    "vocal_pause_after_sec": 0.3,
                    "mix_note": sb_defaults.get("mix_note", ""),
                    "freesound_keywords": [],
                },
            }
            for b in template["beats"]
        ],
    }
    # Sub-genre-specific extra rules
    if "anti_plagiarism_rule" in template:
        config["anti_plagiarism_rule"] = template["anti_plagiarism_rule"]
    if "original_only_rule" in template:
        config["original_only_rule"] = template["original_only_rule"]

    atomic_write_json(out_path, config, indent=2)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True,
                        help="SY_NN_<S|R|H>_<slug> case id from story_queue/")
    parser.add_argument("--out", type=Path, default=None,
                        help="Override output path (default: output/scripts/<case>/script_config.json)")
    args = parser.parse_args()

    out = scaffold_script_config(args.case, args.out)
    print(f"  ✓ scaffold written: {out.relative_to(PROJECT_ROOT) if out.is_relative_to(PROJECT_ROOT) else out}")
    print(f"  next: have Claude fill in title, beat texts, keywords, then run")
    print(f"  check_script_structure.py --case {args.case} --fail-fast")


if __name__ == "__main__":
    main()
