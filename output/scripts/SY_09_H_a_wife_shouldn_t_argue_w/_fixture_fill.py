"""Test fixture — hand-fills the SY_09 script_config briefs for E2E validation.

This isn't part of the production pipeline. It exists so we can verify the
storyboard-first plumbing (validator → visuals → audio → sound design) works
end-to-end without waiting for the daily-shorts-pipeline routine to fire.

Delete or ignore once the pipeline owns the writer step.
"""
import json
import sys
from pathlib import Path

config_path = Path(__file__).resolve().parent / "script_config.json"
cfg = json.loads(config_path.read_text())

# Original horror micro-fiction inspired by the structural shape (NOT prose) of
# r/shortscarystories/1tgpxpr. Premise: a wife notices her husband disagree
# with her once — and then nothing in the house disagrees with him again.
filled = [
    {
        "label": "hook",
        "text": "He smiled. The lamp dimmed when I disagreed back.",
        "keywords": ["lamp", "shadow", "kitchen night"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "frozen dread, breath-held",
            "subject": "kitchen lamp casting a single circle of light on a dining table, husband's silhouette half-visible at the edge",
            "framing": "low-angle medium shot, table-level, husband off-center right",
            "lens": "35mm, shallow DOF",
            "lighting": "single warm lamp overhead, hard shadow underneath, everything else black",
            "color": "near-monochrome, blue-black shadow, single warm highlight on the table",
            "props": ["dining table", "lamp", "two coffee cups", "empty chair"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "anime", "smiling", "ghost imagery", "bright color"],
            "stock_keywords": ["dark kitchen lamp", "single light table", "night kitchen interior"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "kitchen room tone, refrigerator hum, distant clock tick, silence-dominant",
            "sfx": [
                {"at_sec": 0.0, "name": "kitchen ambient stop sudden", "gain_db": -6},
            ],
            "music_cue": "no music",
            "music_intensity": 0.2,
            "vocal_mood": "tight whisper, slow tempo, breath audible on the reveal",
            "vocal_pause_after_sec": 0.6,
            "mix_note": "ambient -22db, sfx hit drops -3db then silence reasserts",
            "freesound_keywords": ["kitchen room tone night", "refrigerator hum quiet", "clock tick wall"],
        },
    },
    {
        "label": "setup",
        "text": "It started small. Two years ago. He asked me to pass the salt. I said in a minute. He didn't speak for the rest of dinner.",
        "keywords": ["dining table", "two place settings", "domestic"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "claustrophobic, normal-turning-wrong",
            "subject": "dining table with two place settings, salt shaker between them, untouched plates of food",
            "framing": "wide overhead shot, top-down, symmetric",
            "lens": "24mm wide, deep focus",
            "lighting": "soft overhead pendant, slightly cool, no shadows",
            "color": "muted greens and creams, low saturation",
            "props": ["salt shaker", "plates", "wine glasses", "linen napkins"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "smiling", "candlelight romance"],
            "stock_keywords": ["dinner table overhead", "two place settings", "untouched dinner"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "dining room ambience, plate clinks, faint cutlery, kitchen extractor distant",
            "sfx": [
                {"at_sec": 1.5, "name": "fork on plate single tap", "gain_db": -12},
            ],
            "music_cue": "very low drone fade in",
            "music_intensity": 0.25,
            "vocal_mood": "tight whisper",
            "vocal_pause_after_sec": 0.3,
            "mix_note": "ambient -20db, sfx subtle",
            "freesound_keywords": ["dinner table cutlery", "dining room ambience", "fork plate tap"],
        },
    },
    {
        "label": "build",
        "text": "Last winter the wall clock stopped at three o'clock. He said it was fine. The clock stayed stopped for eleven months.",
        "keywords": ["wall clock", "stopped hands", "dim hallway"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "dread, time-locked",
            "subject": "vintage wall clock with hands frozen at three, mounted on cracked wallpaper",
            "framing": "medium close-up, slightly off-axis right, clock centered",
            "lens": "50mm, shallow DOF",
            "lighting": "weak window light from frame left, dust visible in beam",
            "color": "dust greys, sepia yellows, deep shadow on the wall edges",
            "props": ["wall clock", "wallpaper cracks", "shelf below clock"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "modern digital displays"],
            "stock_keywords": ["vintage wall clock", "old clock face stopped", "broken clock dim room"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "house at night, low wind through walls, no other sound",
            "sfx": [
                {"at_sec": 2.0, "name": "clock tick single missing", "gain_db": -8},
            ],
            "music_cue": "low drone deepening, ascending",
            "music_intensity": 0.3,
            "vocal_mood": "tight whisper, slower",
            "vocal_pause_after_sec": 0.4,
            "mix_note": "ambient -18db, sfx duck VO -3db",
            "freesound_keywords": ["house wind low", "clock tick missed", "old house creak"],
        },
    },
    {
        "label": "mid_anchor",
        "text": "Eleven months of nothing breaking, nothing creaking, nothing disagreeing. Then I told him no, actually, I won't.",
        "keywords": ["closed door bedroom", "hand on knob", "shadow stretching"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "frozen, sub-zero dread, the moment everything pivots",
            "subject": "closed bedroom door at end of dark hallway, a single hand on the doorknob from camera POV",
            "framing": "POV first-person, narrow hallway compressing toward the door, low height",
            "lens": "28mm wide, sharp deep focus, slight vignette",
            "lighting": "single overhead bulb fifty feet behind camera, door is the brightest object",
            "color": "deep blue-black hallway, warm bulb glow only on the door, hand silhouette dark",
            "props": ["doorknob", "hallway floor", "doorframe", "wallpaper edge"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "anime", "ghost imagery", "wide-eyed shock"],
            "stock_keywords": ["dark hallway door night", "doorknob first person", "long hallway closed door"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "complete silence, single distant refrigerator hum, room tone -28db",
            "sfx": [
                {"at_sec": 3.0, "name": "doorknob hand contact gentle", "gain_db": -10},
            ],
            "music_cue": "music spike to peak then ABRUPT silence on 'no, actually, I won't'",
            "music_intensity": 0.75,
            "vocal_mood": "tight whisper, almost breathless, slower than baseline on the pivot",
            "vocal_pause_after_sec": 0.8,
            "mix_note": "music sidechain to VO, ABRUPT cut to silence on the word 'won't', let silence breathe",
            "freesound_keywords": ["empty house silence", "doorknob soft", "deep silence room tone"],
        },
    },
    {
        "label": "expand",
        "text": "The lamp dimmed. The fridge hum cut. Every wall held its breath. And he smiled again, slower this time.",
        "keywords": ["dim lamp", "still kitchen", "shadow growing"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "house-as-organism, dread compounding",
            "subject": "kitchen lamp visibly dimming mid-frame, surrounding shadows growing inward",
            "framing": "medium wide, eye-level, lamp centered, edges falling to black",
            "lens": "35mm, shallow DOF on the lamp",
            "lighting": "single lamp source actively dimming through the shot, no fill",
            "color": "warm orange dying into blue-black at the edges",
            "props": ["kitchen lamp", "countertop", "fridge edge"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "smiling", "anime"],
            "stock_keywords": ["dim kitchen lamp", "lamp going out", "kitchen night dark"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "fridge hum cuts to dead silence at 0:01, then thin distant air pressure",
            "sfx": [
                {"at_sec": 1.0, "name": "fridge hum stops mid-cycle", "gain_db": -8},
                {"at_sec": 4.5, "name": "wood floor creak slow", "gain_db": -12},
            ],
            "music_cue": "low drone returns at lower intensity, sustained",
            "music_intensity": 0.5,
            "vocal_mood": "tight whisper, slower, more breath",
            "vocal_pause_after_sec": 0.5,
            "mix_note": "ambient hard cut on fridge stop, music creeps back in, VO dominant",
            "freesound_keywords": ["fridge hum stop", "wood floor creak slow", "house silence pressure"],
        },
    },
    {
        "label": "payoff",
        "text": "Whatever lives in this house with us, my husband taught it the rules. I learned them too late.",
        "keywords": ["bedroom door reflected", "single warm bulb", "looking back"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "trapped, resigned, terminal",
            "subject": "dim hallway reflection in a darkened mirror, doorknob centered, no figure visible",
            "framing": "tight close-up of mirror surface, slight angle, doorknob reflection sharp",
            "lens": "85mm portrait, shallow DOF",
            "lighting": "single warm bulb behind the mirror caster, mirror itself dim",
            "color": "deep amber on doorknob, surrounding void blue-black",
            "props": ["mirror frame", "doorknob reflection", "hallway wall reflection"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "anime", "ghost figures", "bright color"],
            "stock_keywords": ["dark mirror reflection", "dim hallway mirror", "doorknob reflection night"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "thin air pressure, distant low rumble, no clock no fridge",
            "sfx": [
                {"at_sec": 3.5, "name": "wood door soft latch close", "gain_db": -10},
            ],
            "music_cue": "sustained low drone, no resolution, holds",
            "music_intensity": 0.6,
            "vocal_mood": "tight whisper, resigned, slowest",
            "vocal_pause_after_sec": 0.4,
            "mix_note": "music sustained under VO, ambient very thin, sfx is the only punctuation",
            "freesound_keywords": ["low rumble distant", "wood latch close", "thin pressure hum"],
        },
    },
    {
        "label": "cta",
        "text": "Don't disagree with the house. Follow if you want the rules.",
        "keywords": ["closed door composition", "lamp circle"],
        "visual_brief": {
            "_FILL_IN": False,
            "mood": "loop-back to hook, same composition different light",
            "subject": "kitchen lamp casting circle on table, mirror match to hook beat composition",
            "framing": "low-angle medium shot identical to hook, husband absent now",
            "lens": "35mm, shallow DOF",
            "lighting": "single warm lamp, slightly brighter than hook, room is empty",
            "color": "near-monochrome with single warm circle",
            "props": ["dining table", "lamp", "two empty chairs"],
            "exclude": ["people", "creatures", "faces", "characters", "cartoon", "smiling"],
            "stock_keywords": ["empty dining table lamp", "single light kitchen night", "two empty chairs"],
        },
        "sound_brief": {
            "_FILL_IN": False,
            "ambient_bed": "back to hook ambient: kitchen room tone, fridge hum returns",
            "sfx": [],
            "music_cue": "drone resolves to single low tone, fades to ambient",
            "music_intensity": 0.4,
            "vocal_mood": "confiding narrator, slightly slower",
            "vocal_pause_after_sec": 0.0,
            "mix_note": "match-cut ambient to hook, music tucks under, VO clean",
            "freesound_keywords": ["kitchen room tone", "fridge hum quiet", "night house ambient"],
        },
    },
]

# Merge filled content into existing scaffold (preserves target_seconds, purpose_hint, etc.)
for i, f in enumerate(filled):
    cfg["beats"][i].update(f)

cfg["title"] = "Don't Disagree With the House"
cfg["description_lead"] = "A wife learns that something in her house punishes any voice that contradicts her husband's."
cfg["spoken_text"] = "\n\n".join(b["text"] for b in cfg["beats"])

config_path.write_text(json.dumps(cfg, indent=2))
print(f"  ✓ filled: {config_path.name}")
print(f"  ✓ beats: {len(cfg['beats'])} all populated with text + visual_brief + sound_brief")
print(f"  next: python scripts/check_script_structure.py --case SY_09_H_a_wife_shouldn_t_argue_w --strict")
