#!/usr/bin/env bash
# Install the project-level slash commands for Claude Code.
# Run ONCE on your Mac after pulling the repo.
#
# Usage:
#   bash scripts/install_claude_commands.sh
#
# What it does:
#   1. Creates .claude/commands/ in the project root (if missing)
#   2. Symlinks each .md file from scripts/claude_commands/ into .claude/commands/
#
# After running, the following work inside `claude` in this folder:
#   /upload-next-video
#   /upload-case <id>
#   /upload-list

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$SCRIPT_DIR/claude_commands"
DST="$PROJECT_ROOT/.claude/commands"

mkdir -p "$DST"

count=0
for f in "$SRC"/*.md; do
  name="$(basename "$f")"
  target="$DST/$name"
  if [ -L "$target" ] || [ -f "$target" ]; then
    rm -f "$target"
  fi
  ln -s "$f" "$target"
  echo "  installed /$(basename "$f" .md)  →  $target"
  count=$((count + 1))
done

echo
echo "✓ Installed $count slash command(s) in $DST"
echo "  Open Claude Code in this folder and try: /upload-list"
