#!/bin/sh
# Install Agent Company into ./agent-company from a release zip URL or a local zip.
#   sh install.sh <zip-url-or-path>
set -e
SRC=${1:?give the release zip URL or a local path}
command -v python3 >/dev/null || { echo "python3 is required (3.9 or later)"; exit 1; }
TMP=$(mktemp -d)
case "$SRC" in
  http*) curl -fsSL "$SRC" -o "$TMP/ac.zip" ;;
  *) cp "$SRC" "$TMP/ac.zip" ;;
esac
unzip -q "$TMP/ac.zip" -d "$TMP/x"
DIR=$(find "$TMP/x" -name agent_company.py -maxdepth 3 | head -1 | xargs dirname)
[ -n "$DIR" ] || { echo "agent_company.py not found in the zip"; exit 1; }
[ -e ./agent-company ] && { echo "./agent-company exists; remove or rename it first"; exit 1; }
cp -R "$DIR" ./agent-company
python3 ./agent-company/agent_company.py --version >/dev/null
echo "Installed ./agent-company. Next: python3 agent-company/agent_company.py init <your-project>"
