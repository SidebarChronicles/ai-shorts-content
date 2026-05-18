#!/usr/bin/env python3
"""Manual-entry revenue tracker for DROP channel monetization.

Per the v2 strategy (May 18 2026), revenue comes from follower-driven paths
(not affiliate clicks). This script captures monthly income from each path
for the cost-vs-revenue break-even rollup.

Platforms tracked:
  - tiktok_creator_rewards   TikTok Creator Rewards Program (need 10K + 100K/30d)
  - youtube_adsense          YouTube Shorts AdSense via YPP (need 500/1k subs + views)
  - brand_deal               One-off paid sponsorships
  - kofi                     One-time Ko-fi tips
  - patreon                  Recurring Patreon pledges
  - other                    Catch-all (merch, compilation deals, etc.)

State file: output/revenue_ledger.json
  {
    "2026-05": {
      "tiktok_creator_rewards": 0.0,
      "youtube_adsense": 0.0,
      "brand_deal": 0.0,
      "kofi": 0.0,
      "patreon": 0.0,
      "other": 0.0,
      "entries": [{"date": "2026-05-18", "platform": "...", "amount": ..., "note": "..."}]
    }
  }

Usage:
    python3 scripts/revenue_tracker.py --add tiktok_creator_rewards 12.50
    python3 scripts/revenue_tracker.py --add brand_deal 250.00 --note "Audible sponsorship"
    python3 scripts/revenue_tracker.py --monthly
    python3 scripts/revenue_tracker.py --break-even-check
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_json  # noqa: E402

LEDGER_FILE = PROJECT_ROOT / "output" / "revenue_ledger.json"
COST_FILES = {
    "elevenlabs": PROJECT_ROOT / "output" / "elevenlabs_usage.json",
    "replicate":  PROJECT_ROOT / "output" / "replicate_usage.json",
}

VALID_PLATFORMS = (
    "tiktok_creator_rewards",
    "youtube_adsense",
    "brand_deal",
    "kofi",
    "patreon",
    "other",
)


def _load_ledger() -> dict:
    if not LEDGER_FILE.exists():
        return {}
    try:
        return json.loads(LEDGER_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_ledger(data: dict) -> None:
    atomic_write_json(LEDGER_FILE, data, indent=2, sort_keys=True)


def _empty_month() -> dict:
    return {p: 0.0 for p in VALID_PLATFORMS} | {"entries": []}


def _current_month_key() -> str:
    return date.today().strftime("%Y-%m")


def cmd_add(platform: str, amount: float, note: str | None = None,
            month: str | None = None) -> None:
    if platform not in VALID_PLATFORMS:
        sys.exit(f"ERROR: platform must be one of {VALID_PLATFORMS}")
    if amount < 0:
        sys.exit(f"ERROR: amount cannot be negative (got {amount})")
    month_key = month or _current_month_key()
    ledger = _load_ledger()
    if month_key not in ledger:
        ledger[month_key] = _empty_month()
    elif "entries" not in ledger[month_key]:
        # Back-fill schema if older ledger format
        for p in VALID_PLATFORMS:
            ledger[month_key].setdefault(p, 0.0)
        ledger[month_key].setdefault("entries", [])
    ledger[month_key][platform] = round(ledger[month_key][platform] + amount, 2)
    ledger[month_key]["entries"].append({
        "date": date.today().isoformat(),
        "platform": platform,
        "amount": amount,
        "note": note or "",
    })
    _save_ledger(ledger)
    total = sum(ledger[month_key][p] for p in VALID_PLATFORMS)
    print(f"  ✓ +${amount:.2f} → {platform} ({month_key})")
    print(f"    Month total: ${total:.2f}")


def cmd_monthly(month: str | None = None) -> None:
    month_key = month or _current_month_key()
    ledger = _load_ledger()
    if month_key not in ledger:
        print(f"  No revenue recorded for {month_key} yet.")
        return
    m = ledger[month_key]
    print(f"\n=== Revenue for {month_key} ===\n")
    print(f"  {'Platform':<28} {'Amount':>10}")
    print(f"  {'-'*28} {'-'*10}")
    total = 0.0
    for platform in VALID_PLATFORMS:
        amount = m.get(platform, 0.0)
        if amount > 0:
            print(f"  {platform:<28} ${amount:>9.2f}")
        total += amount
    print(f"  {'-'*28} {'-'*10}")
    print(f"  {'TOTAL':<28} ${total:>9.2f}")

    entries = m.get("entries", [])
    if entries:
        print(f"\n  {len(entries)} entry/entries this month")


def _load_monthly_cost() -> dict:
    """Read EL + Replicate usage for the current month."""
    month_key = _current_month_key()
    costs = {"elevenlabs": 0.0, "replicate": 0.0}
    for name, path in COST_FILES.items():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            month_data = data.get(month_key, {})
            # both files use {"usd": float} shape
            costs[name] = float(month_data.get("usd", 0.0))
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            pass
    return costs


def cmd_break_even_check() -> None:
    month_key = _current_month_key()
    ledger = _load_ledger()
    revenue = 0.0
    if month_key in ledger:
        revenue = sum(ledger[month_key].get(p, 0.0) for p in VALID_PLATFORMS)
    costs = _load_monthly_cost()
    total_cost = sum(costs.values())

    print(f"\n=== Break-even check for {month_key} ===\n")
    print(f"  Costs (month-to-date):")
    for name, amount in costs.items():
        print(f"    {name:<14} ${amount:>9.2f}")
    print(f"    {'TOTAL COSTS':<14} ${total_cost:>9.2f}")
    print()
    print(f"  Revenue (month-to-date):")
    print(f"    {'TOTAL REVENUE':<14} ${revenue:>9.2f}")
    print()
    gap = revenue - total_cost
    if gap >= 0:
        print(f"  ✓ Above break-even by ${gap:.2f}")
    else:
        # Estimate days to break-even at current revenue burn
        days_in_month = 30
        today_day = date.today().day
        if today_day > 0 and revenue > 0:
            daily_rev = revenue / today_day
            days_to_cover = total_cost / daily_rev if daily_rev > 0 else float("inf")
            print(f"  ✗ Gap: ${-gap:.2f}  (revenue/day so far: ${daily_rev:.2f})")
            if days_to_cover < days_in_month * 6:
                print(f"     At current pace: ~{days_to_cover:.0f} days to break-even on this month's costs")
        else:
            print(f"  ✗ Gap: ${-gap:.2f}  (no revenue yet this month)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--add", nargs=2, metavar=("PLATFORM", "AMOUNT"),
                   help=f"Add a revenue entry. Platform: one of {VALID_PLATFORMS}")
    g.add_argument("--monthly", action="store_true", help="Show this month's revenue breakdown")
    g.add_argument("--break-even-check", action="store_true",
                   help="Compare month-to-date costs vs revenue")
    parser.add_argument("--month", default=None,
                        help="Override month key (format YYYY-MM, defaults to current)")
    parser.add_argument("--note", default=None, help="Optional note for --add")
    args = parser.parse_args()

    if args.add:
        platform, amount_str = args.add
        try:
            amount = float(amount_str)
        except ValueError:
            sys.exit(f"ERROR: amount must be a number (got {amount_str!r})")
        cmd_add(platform, amount, args.note, args.month)
    elif args.monthly:
        cmd_monthly(args.month)
    elif args.break_even_check:
        cmd_break_even_check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
