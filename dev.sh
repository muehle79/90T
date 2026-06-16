#!/bin/bash
# Lokaler Entwicklungsserver — startet die App unter http://192.168.178.110:8080
set -e
cd "$(dirname "$0")"

# Static-Symlink sicherstellen (zeigt auf Repo-Root)
if [ ! -L server/static ] || [ "$(readlink server/static)" != "$(pwd)" ]; then
    ln -sfn "$(pwd)" server/static
fi

# .env laden
export $(grep -v '^#' server/.env | xargs)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Entwicklungsserver"
echo " http://192.168.178.110:8080"
echo " Stoppen: Ctrl+C"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

server/venv/bin/python server/app.py
