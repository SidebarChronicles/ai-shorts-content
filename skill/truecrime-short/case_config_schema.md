# Case Config Schema

Each case has a `case_config.json` that drives the generalized renderer. Schema:

```json
{
  "case_id": "02_ransomware_negotiator",
  "audio_file": "assets/audio/narration_02.aiff",
  "header_line_1": "U.S. DISTRICT COURT · SOUTHERN DISTRICT OF FLORIDA",
  "header_line_2": "CASE 26-383 · UNITED STATES v. MARTINO",
  "segments": [
    {
      "name": "hook",
      "word_count": 24,
      "chunks": ["WHEN HACKERS COULDN'T", "TRICK THEIR VICTIMS", ...]
    },
    ...
  ],
  "scenes": [
    {
      "type": "title",
      "label": "THE CASE OF",
      "main": "ANGELO MARTINO",
      "subline_top": "AGE 41 · LAND O'LAKES, FL",
      "subline_bottom": "CYBERSECURITY NEGOTIATOR"
    },
    {
      "type": "three_step",
      "header": "THE BETRAYAL",
      "steps": [["01", "HIRED"], ["02", "BETRAYED"], ["03", "EXTORTED"]]
    },
    {
      "type": "big_stat",
      "label": "BLACKCAT RANSOMS",
      "value": "$1.2M",
      "value_color": "red",
      "subline_top": "EXTORTED FROM ONE VICTIM",
      "subline_bottom": "SPLIT THREE WAYS",
      "boxes": [
        ["INSURANCE LIMITS", "LEAKED"],
        ["NEGOTIATION POSITIONS", "LEAKED"],
        ["5 VICTIMS", "SOLD OUT"]
      ]
    },
    {
      "type": "receipt",
      "header": "ASSETS SEIZED — $10M",
      "items": [
        ["DIGITAL CURRENCY", "SEIZED"],
        ["VEHICLES", "SEIZED"],
        ["FOOD TRUCK", "SEIZED"],
        ["LUXURY FISHING BOAT", "SEIZED"]
      ]
    },
    {
      "type": "location",
      "beat_label": "BREAK-IN",
      "date": "FEB · 2024",
      "place": "WINNSBORO, TEXAS",
      "shape": "bullseye",
      "stat_label": "STOLEN",
      "stat_value": "100 BTC",
      "stat_sub": "≈ $5,000,000"
    },
    {
      "type": "outcome",
      "header": "FACES",
      "months": "20",
      "months_unit": "YEARS",
      "restitution_label": "STATUTORY MAX",
      "restitution_value": "SENTENCING JULY 9, 2026"
    }
  ]
}
```

## Scene types

| Type | Required fields |
|---|---|
| `title` | `label`, `main`, `subline_top`, `subline_bottom` |
| `big_stat` | `label`, `value`, `value_color` (red/yellow/white), `subline_top`, `subline_bottom`, optional `boxes` (3-tuple of `[top, bottom]`) |
| `location` | `beat_label`, `date`, `place`, `shape` (bullseye/map/pin), `stat_label`, `stat_value`, `stat_sub` |
| `three_step` | `header`, `steps` (3-tuple of `[num, label]`) |
| `receipt` | `header`, `items` (list of `[left, right]`) |
| `outcome` | `header`, `months`, `months_unit` (MONTHS/YEARS), `restitution_label`, `restitution_value` |

## Segment shape

Each `segments` entry corresponds to one of the six narration beats. The renderer:
1. Reads `word_count` for proportional time allocation
2. Reads `chunks` (2-3 word phrases) for ASS-style captions
3. Distributes chunks evenly across the segment's time window
4. Bakes captions into per-chunk PNGs over the matching scene background

## Audio timing math

```python
AUDIO = ffprobe_duration("assets/audio/narration_NN.aiff")
SEG_WORDS = [s["word_count"] for s in segments]  # 6 ints
N_PAUSES = 5
PAUSE = 0.5
SPEECH = AUDIO - N_PAUSES * PAUSE
WPS = sum(SEG_WORDS) / SPEECH
seg_speech = [w / WPS for w in SEG_WORDS]
```

Scene N gets duration = seg_speech[N] + (PAUSE if N < 5 else 0).
