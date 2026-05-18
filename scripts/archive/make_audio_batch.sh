#!/usr/bin/env bash
# Batch-generate narration audio for cases 02-06 using macOS `say`.
# Run this ON YOUR MAC (not from Claude). Takes ~20-30 seconds total.
#
# Usage:
#   bash scripts/make_audio_batch.sh
#
# Outputs (all written to assets/audio/):
#   narration_02.aiff   Ransomware Negotiator
#   narration_03.aiff   Fugitive Crypto Scam
#   narration_04.aiff   Cargo Heist
#   narration_05.aiff   NFL Medicare Fraud
#   narration_06.aiff   Genetic Testing Fraud
#
# Voice / rate (override with env vars to match case 01):
#   VOICE=Daniel  RATE=180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/assets/audio"
mkdir -p "$OUT_DIR"

VOICE="${VOICE:-Daniel}"
RATE="${RATE:-180}"

echo "Voice: $VOICE  ·  Rate: $RATE wpm"
echo "Out:   $OUT_DIR"
echo

# ---------------------------------------------------------------------------
# CASE 02 — Ransomware Negotiator
# ---------------------------------------------------------------------------
read -r -d '' NARR_02 <<'EOF' || true
His clients hired him to fight the ransomware gang attacking them. He was secretly working for the gang. [[slnc 500]]

Angelo Martino, forty-one, of Land O'Lakes Florida, worked as a ransomware negotiator at a U.S. cyber incident response firm. Five victims paid his employer to bargain down BlackCat ransom demands. [[slnc 500]]

Instead, Martino sold BlackCat each victim's insurance policy limits — and their internal negotiating strategy. The hackers paid him for it. The ransoms went up. [[slnc 500]]

Then he joined the conspiracy outright. With two co-defendants, he deployed BlackCat ransomware against new American victims — extorting one company for one point two million dollars in bitcoin. They split the ransom three ways. [[slnc 500]]

Federal agents seized ten million dollars of his assets. Digital currency. Vehicles. A food truck. A luxury fishing boat. [[slnc 500]]

This April, Martino pleaded guilty to conspiracy to commit extortion. He faces up to twenty years in federal prison. He is scheduled to be sentenced this July.
EOF

# ---------------------------------------------------------------------------
# CASE 03 — Fugitive Crypto Scam
# ---------------------------------------------------------------------------
read -r -d '' NARR_03 <<'EOF' || true
He pleaded guilty. Then he cut off his ankle monitor and ran. Today, a federal judge sentenced him to twenty years — to an empty chair. [[slnc 500]]

Daren Li, forty-two, ran the laundering arm of a Cambodian crypto scam. Operatives reached American victims through unsolicited social media, phone calls, and dating apps. They built fake romantic or professional relationships over weeks, communicating on encrypted apps. [[slnc 500]]

Then came the fake trading platform — spoofed websites that mimicked legitimate crypto exchanges. Victims invested. The money vanished. Seventy-three million dollars in victim funds were routed through bank accounts Li controlled — nearly sixty million laundered through U.S. shell companies. [[slnc 500]]

Li pleaded guilty in November twenty twenty-four. In December, he cut off his ankle monitor and disappeared. He's a fugitive. [[slnc 500]]

This February, sentenced in absentia. The statutory maximum — twenty years. Eight co-conspirators have already pleaded guilty.
EOF

# ---------------------------------------------------------------------------
# CASE 04 — Cargo Heist
# ---------------------------------------------------------------------------
read -r -d '' NARR_04 <<'EOF' || true
They followed Meta and Microsoft trucks out of the loading dock. When the driver stopped for fuel, they drove off with the whole trailer. [[slnc 500]]

For eighteen months, a six-man crew operated out of Florida and Kentucky. They traveled to distribution facilities in Indiana, Kentucky, and Ohio. Meta. Microsoft. L Brands. They watched the loading docks. Tailed the trucks. [[slnc 500]]

When a driver stopped to rest, the crew stole the entire tractor-trailer. Then they swapped tractors, painted over the logos, and changed the license plates. The cargo went to a Miami buyer for a fraction of retail. [[slnc 500]]

Fourteen separate heists. Two million dollars in Oculus VR headsets. Nine hundred forty thousand in Microsoft products. One million in Bath and Body Works and Victoria's Secret merchandise. Six hundred sixty-nine thousand in Harmon-JBL audio. Four hundred eighty thousand in Bose speakers. [[slnc 500]]

All sold in Miami for a fraction of retail value to known buyers. [[slnc 500]]

This January, ringleader Juan Perez-Gonzalez was sentenced to thirteen and a half years in federal prison. Five co-defendants received sentences from time served to nearly eight years.
EOF

# ---------------------------------------------------------------------------
# CASE 05 — NFL Player Medicare Fraud
# ---------------------------------------------------------------------------
read -r -d '' NARR_05 <<'EOF' || true
He played in the NFL. Then he stole one hundred ninety-seven million dollars from elderly Americans and disabled veterans. [[slnc 500]]

Joel Rufus French, forty-seven, owned a marketing company and eight medical equipment companies — all hidden behind straw owners. Overseas telemarketing call centers pressured seniors into agreeing to medical braces they didn't need. When seniors refused, the call centers altered the recordings to fake consent. [[slnc 500]]

French paid sham telemedicine companies for fake doctors' orders. Doctors who had never examined the patients. Often never spoken to them. Then he billed Medicare and CHAMPVA — the program for the families of disabled veterans. [[slnc 500]]

Two hundred and twenty-five thousand dollars in cash, laundered through a Mississippi bank. Ten thousand at a time, driven to Orlando in a bag, to pay informants for victims' insurance information. [[slnc 500]]

A federal jury convicted him in February. This month — one hundred ninety-six months in prison. One hundred ten million in restitution. Seventeen million forfeited.
EOF

# ---------------------------------------------------------------------------
# CASE 06 — Genetic Testing Fraud
# ---------------------------------------------------------------------------
read -r -d '' NARR_06 <<'EOF' || true
They knocked on doors. They asked for your DNA. Then they billed Medicare five hundred and twenty-two million dollars. [[slnc 500]]

Reyad Salahaldeen, fifty-seven, of Buford Georgia, controlled four laboratories across New Jersey, Georgia, and Texas. From twenty eighteen to twenty twenty, he paid kickbacks to a network of marketers. [[slnc 500]]

They harvested DNA from elderly Americans — through telemarketing, door-to-door solicitation, and health fairs. [[slnc 500]]

The DNA was for expensive genetic tests. To make them billable, Salahaldeen paid doctors and nurse practitioners for signed orders. Doctors who had never treated the patients. Often never met them. [[slnc 500]]

When federal agents came with an arrest warrant, Salahaldeen drove from North Carolina to Texas and tried to cross into Mexico — using another person's identification. He was caught at the border. [[slnc 500]]

Five hundred and twenty-two million billed. Eighty-four million actually paid by Medicare and Medicaid. This month: one hundred fifty-one months in federal prison. Eighty-four million in restitution. Eleven co-conspirators have already pleaded guilty.
EOF

# Generate all 5
for IDX in 02 03 04 05 06; do
  VAR="NARR_${IDX}"
  OUT="$OUT_DIR/narration_${IDX}.aiff"
  echo -n "→ Generating narration_${IDX}.aiff ... "
  say -v "$VOICE" -r "$RATE" -o "$OUT" "${!VAR}"
  DUR=$(afinfo "$OUT" 2>/dev/null | awk '/estimated duration/ {print $3}' || echo "?")
  echo "✓ (${DUR}s)"
done

echo
echo "All 5 narrations generated."
echo "Tell Claude 'audio batch ready' and the 5 mp4s + descriptions will be rendered."
