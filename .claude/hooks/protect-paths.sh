#!/usr/bin/env bash
# PreToolUse hook for Edit|Write: refuse writes to paths that must never be edited by an agent.
# Reads the tool call JSON on stdin; exit 2 blocks the call and returns stderr to the agent.
set -u
path=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
[ -z "$path" ] && exit 0
case "$path" in
  */outputs/*|outputs/*|*/.venv*|.venv*|*/calibration/*|*.ckpt|*.pt|*.pth|*.safetensors|*.mp4|*.mov|*/.claude/hooks/*|*/.claude/settings.json)
    echo "blocked: '$path' is a protected path (run artifacts, venvs, calibration, checkpoints, media, or the hooks themselves). Edit it by hand if it really needs to change." >&2
    exit 2 ;;
esac
exit 0
