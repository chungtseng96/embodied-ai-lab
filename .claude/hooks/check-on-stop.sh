#!/usr/bin/env bash
# Stop hook: the turn may not end with failing tests or lint on LaundryBench Python.
# Runs only when Python under projects/laundrybench/ changed, so docs-only turns are free.
# Exit 2 sends stderr back to the agent as the reason it cannot stop yet.
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 0

changed=$( { git diff --name-only; git diff --name-only --cached; git ls-files --others --exclude-standard; } 2>/dev/null \
  | grep -E '^projects/laundrybench/.*\.py$' | sort -u)
[ -z "$changed" ] && exit 0

python=".venv/bin/python"
[ -x "$python" ] || python="python3"

if ! out=$(make check PYTHON="$python" 2>&1); then
  {
    echo "make check failed; fix before finishing. Changed Python files:"
    echo "$changed"
    echo "$out" | tail -40
  } >&2
  exit 2
fi
exit 0
