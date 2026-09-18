#!/usr/bin/env bash
# PostToolUse hook: run ruff on any .py file Claude just wrote or edited.
# Self-gating: exits 0 silently for non-Python files or when ruff is missing.
# Uses the project venv if present so the result matches `make lint`.
set -u
input=$(cat)
tool=$(echo "$input" | jq -r '.tool_name // ""')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

[[ "$tool" == "Write" || "$tool" == "Edit" ]] || exit 0
[[ "$file_path" == *.py ]] || exit 0
[[ -f "$file_path" ]] || exit 0

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
py="$root/projects/laundrybench/.venv/bin/python"
[[ -x "$py" ]] || py=python3
"$py" -m ruff --version >/dev/null 2>&1 || exit 0

if ! out=$("$py" -m ruff check --fix "$file_path" 2>&1); then
  echo "<ruff_errors>"
  echo "ruff found unfixable issues in $file_path. Fix them, then run \`make lint\` from the repo root."
  echo "$out"
  echo "</ruff_errors>"
fi
exit 0
