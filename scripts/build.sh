#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dist_dir="$repo_root/dist"
stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/agent-launcher.XXXXXX")"
trap 'rm -rf "$stage_dir"' EXIT

"$repo_root/scripts/test.sh"
mkdir -p "$dist_dir"
rm -f "$dist_dir/Agent-Launcher.alfredworkflow" "$dist_dir/Agent-Launcher.alfredworkflow.sha256"

cp "$repo_root/source/info.plist" "$stage_dir/info.plist"
cp "$repo_root/source/query.py" "$stage_dir/query.py"
cp "$repo_root/source/launch.py" "$stage_dir/launch.py"
cp "$repo_root/source/icon.png" "$stage_dir/icon.png"
cp "$repo_root/source/icon-codex.png" "$stage_dir/icon-codex.png"
cp "$repo_root/source/icon-claude.png" "$stage_dir/icon-claude.png"

(
  cd "$stage_dir"
  zip -q "$dist_dir/Agent-Launcher.alfredworkflow" \
    info.plist query.py launch.py icon.png icon-codex.png icon-claude.png
)

(
  cd "$dist_dir"
  shasum -a 256 Agent-Launcher.alfredworkflow > Agent-Launcher.alfredworkflow.sha256
)

echo "$dist_dir/Agent-Launcher.alfredworkflow"
