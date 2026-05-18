# Safety Rules — TrueCrime Shorts

Applied after the writer pass, before video assembly. Any failure → revise script.

## Hard blocklist (auto-fail on substring match)

These phrases signal weak factual ground or unconvicted assertions:

- "allegedly killed"
- "is believed to have"
- "experts say"
- "could be"
- "may have"
- "sources suggest"
- "it's possible that"
- "reportedly committed"

## Classifier categories (score 0–5, threshold 2)

### `defamation_risk`
- 0 — All subjects convicted/pleaded guilty; conduct described matches source
- 2 — Some indicted defendants named (acceptable if source confirms charges)
- 5 — Naming uncharged people, asserting unproven facts, alleging conduct beyond the source

### `graphic_violence`
- 0 — No violence described
- 1 — Property crime details (brick, broken window, theft) — neutral
- 2 — Weapons referenced (firearms found, etc.) — neutral
- 3 — Acts of violence against persons — described matter-of-factly
- 5 — Sensationalized violence, lurid detail

### `victim_identifying`
- 0 — Victims unnamed, only city/state level locations
- 2 — Specific occupation or age range mentioned
- 5 — Name, address, photo, or details narrow enough to identify

### `sexual_content`
- 0 — None
- 5 — Any depiction or explicit reference

## When a score exceeds 2

Revise the script. Common fixes:
- Replace named indicted-but-not-convicted person with "the defendant"
- Drop sensational adverbs
- Generalize victim descriptors (city-level not specific)
- Remove speculative motive language

## Hard skip rules (case-level)

Skip these cases entirely during Phase 0 selection (don't even script them):

- Any case with minor (under-18) victims
- Sexual violence as the primary element
- Ongoing investigation (no conviction or guilty plea yet)
- Cases involving identified victims who have publicly objected to coverage
- Cases that could plausibly target a specific living person not yet adjudicated

## Reviewer's eye

After scoring, ask: "If the defendant's lawyer saw this video, could they reasonably claim defamation?" If the answer is anything other than "no, every claim ties to public court records," the script is not ready.
