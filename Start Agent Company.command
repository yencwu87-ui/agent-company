#!/bin/sh
# Mac: double-click this file to start Agent Company. It makes your first project folder
# (~/agent-company-projects/my-first-team), sets everything up, and opens the World in your browser.
# The first time, macOS may ask: right-click this file, choose Open, then Open again.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 isn't installed. Install it from https://www.python.org/downloads/ and double-click this file again."
  read -r _; exit 1
fi
python3 agent_company.py launch "$@"
echo; echo "Agent Company stopped. You can close this window."; read -r _
