#!/bin/bash
# Launch the visualizer fullscreen in a tmux session (reattaches if one is
# already running). The config comes from data/active_config — written by the
# config web UI's "apply" button — falling back to test1.json.
cd "$(dirname "$(readlink -f "$0")")"
export LANG=C.UTF-8

CFG=test1.json
if [ -f data/active_config ]; then
    CANDIDATE=$(head -1 data/active_config | tr -d '[:space:]')
    [ -f "data/configs/$CANDIDATE" ] && CFG=$CANDIDATE
fi

PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

exec tmux new-session -A -s vis "$PY main.py $CFG"
