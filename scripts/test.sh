#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

plutil -lint "$repo_root/source/info.plist"
PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/agent-launcher-pycache" \
  /usr/bin/python3 -m py_compile \
  "$repo_root/source/query.py" \
  "$repo_root/source/launch.py"

PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/agent-launcher-pycache" \
  /usr/bin/python3 -m unittest discover -s "$repo_root/tests" -v
