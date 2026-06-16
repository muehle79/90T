#!/bin/bash
# Deploy-Skript für 90TC auf dem Raspberry Pi
# Einmalige Vorbereitung: git clone https://github.com/muehle79/90T.git /home/pi/90tc-repo
# Aufruf: /home/pi/deploy.sh  (oder: bash /home/pi/90tc-repo/server/deploy.sh)
set -e

REPO=/home/pi/90tc-repo
STATIC=/home/pi/90tc-app/static
APP=/home/pi/90tc-app

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Pull ───────────────────────────────────
echo "[1/3] Pull von GitHub..."
git -C "$REPO" pull

# ── 2. Statische Dateien kopieren ────────────
echo "[2/3] Statische Dateien kopieren..."
for f in index.html sw.js manifest.json import.html export.html \
          icon-192.png icon-512.png favicon.png; do
  [ -f "$REPO/$f" ] && cp "$REPO/$f" "$STATIC/$f" && echo "  ✓ $f"
done

# ── 3. Backend — nur neu starten wenn app.py geändert ──
echo "[3/3] Backend prüfen..."
BACKEND_CHANGED=false
for f in app.py setup_db.py; do
  SRC="$REPO/server/$f"
  DST="$APP/$f"
  if [ -f "$SRC" ]; then
    if [ ! -f "$DST" ] || ! cmp -s "$SRC" "$DST"; then
      cp "$SRC" "$DST"
      echo "  ✓ $f aktualisiert"
      BACKEND_CHANGED=true
    else
      echo "  – $f unverändert"
    fi
  fi
done

if [ "$BACKEND_CHANGED" = true ]; then
  echo "  → Python-Pakete aktualisieren..."
  "$APP/venv/bin/pip" install --quiet pywebpush 2>/dev/null || true
  echo "  → Datenbank-Schema aktualisieren..."
  "$APP/venv/bin/python" "$APP/setup_db.py"
  echo "  → Service wird neugestartet..."
  sudo systemctl restart 90tc.service
  sleep 2
  STATUS=$(systemctl is-active 90tc.service)
  if [ "$STATUS" = "active" ]; then
    echo "  ✓ 90tc.service läuft wieder"
  else
    echo "  ✗ Service nicht aktiv — Logs:"
    sudo journalctl -u 90tc.service -n 20 --no-pager
    exit 1
  fi
else
  echo "  – Kein Neustart nötig"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Deploy abgeschlossen ✓"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
