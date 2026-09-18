#!/usr/bin/env bash
# PostToolUse hook: run ruff --fix on any .py file Claude just wrote or edited.
#
# Self-gating: exits 0 silently for non-Python files or when ruff is missing.
# Uses the project venv if present so the result matches `make lint`.
#
# Feedback contract: plain stdout on exit 0 is NOT shown to Claude (only the
# transcript view). To reach Claude without blocking, emit the documented JSON
# `hookSpecificOutput.additionalContext` on stdout and exit 0.
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

before=$(shasum "$file_path")
out=$("$py" -m ruff check --fix "$file_path" 2>&1)
status=$?
after=$(shasum "$file_path")

msg=""
if [[ "$before" != "$after" ]]; then
  msg+="ruff --fix modified $file_path; re-read it before editing again."$'\n'
fi
if [[ $status -ne 0 ]]; then
  msg+="ruff found unfixable issues in $file_path. Fix them, then run \`make lint\` from the repo root."$'\n'
  msg+="$out"
fi
[[ -n "$msg" ]] || exit 0

jq -n --arg ctx "$msg" '{
  hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: $ctx }
}'
exit 0
