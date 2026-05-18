#!/usr/bin/env bash
# Generate the GothFerrari narration audio using macOS `say`.
# Run this ON YOUR MAC (not from Claude). It takes ~3 seconds.
#
# Usage:
#   bash scripts/make_audio.sh
#
# Output:
#   assets/audio/narration.aiff  (uncompressed AIFF — pristine quality, ~5MB)
#
# Voice options (override with env vars):
#   VOICE=Daniel  # British male (default) — fits documentary tone
#   VOICE=Alex    # American male, also great
#   VOICE=Tom     # American male, deeper
#   RATE=180      # words per minute (default; bump to 200 if too slow)
#
# Examples:
#   VOICE=Alex bash scripts/make_audio.sh
#   RATE=200 bash scripts/make_audio.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/assets/audio"
OUT="$OUT_DIR/narration.aiff"

mkdir -p "$OUT_DIR"

VOICE="${VOICE:-Daniel}"
RATE="${RATE:-180}"

# Narration text. Numbers are spelled out so `say` reads them naturally.
# [[slnc N]] inserts an N-millisecond pause for pacing.
read -r -d '' NARRATION <<'EOF' || true
When hackers couldn't trick their victims into handing over their crypto, they called Marlon Ferro. He'd break into your house and take it. [[slnc 500]]

Ferro, twenty, was the so-called instrument of last resort for a two hundred and fifty million dollar social engineering ring. When victims stored their crypto on hardware wallets — devices that can't be hacked remotely — the enterprise sent him in. [[slnc 500]]

February twenty twenty four. Winnsboro, Texas. Ferro broke into a home and walked out with one hundred bitcoin. More than five million dollars. [[slnc 500]]

July twenty twenty four. New Mexico. He staked out the house for days. When co-conspirators tracked the victim's iCloud and confirmed he was gone, Ferro smashed a window with a brick. The home camera caught him. [[slnc 500]]

The stolen money bought Hermès Birkin bags, exotic cars up to three point eight million dollars, nightclub tabs of half a million a night, and private jets. [[slnc 500]]

Ferro was arrested with two firearms and a fake ID. This month, a federal judge sentenced him to seventy eight months in prison — and two point five million dollars in restitution.
EOF

echo "Generating narration..."
echo "  Voice: $VOICE"
echo "  Rate:  $RATE wpm"
echo "  Out:   $OUT"
echo

say -v "$VOICE" -r "$RATE" -o "$OUT" "$NARRATION"

# Print duration so you know the timing
DURATION=$(afinfo "$OUT" 2>/dev/null | awk '/estimated duration/ {print $3}' || echo "?")
echo
echo "Done. Estimated duration: ${DURATION}s"
echo
echo "Next: tell Claude 'audio ready' and the final mp4 will be rendered."
