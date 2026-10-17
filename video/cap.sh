#!/bin/sh
# Capture the full screen (Chrome in front) at Retina resolution: cap.sh <name>
cd "$(dirname "$0")/public/shots" && osascript -e 'tell application "Google Chrome" to activate' && sleep ${2:-1.2} && screencapture -x -o "$1.png" && echo "$1.png"
