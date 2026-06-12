#!/bin/bash
# 90TC Install-Skript für Raspberry Pi (Debian 12)
# Führt Phase 3–7 des Migrationsplans durch
# Aufruf: bash install.sh
set -e

APP=/home/pi/90tc-app
REPO="https://github.com/muehle79/90T.git"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Install-Skript"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Schritt 1: Verzeichnisstruktur
echo "[1/8] Verzeichnisse anlegen..."
mkdir -p "$APP"/{db,static,backups}

# Schritt 2: App-Dateien kopieren (vom Script-Verzeichnis)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[2/8] App-Dateien kopieren..."
cp "$SCRIPT_DIR/app.py"       "$APP/app.py"
cp "$SCRIPT_DIR/setup_db.py"  "$APP/setup_db.py"

# Schritt 3: Statische PWA-Dateien vom GitHub-Repo holen
echo "[3/8] PWA-Dateien vom GitHub-Repo laden..."
TMP_REPO=$(mktemp -d)
git clone --depth=1 "$REPO" "$TMP_REPO/repo" 2>&1 | tail -1
for f in index.html sw.js manifest.json import.html icon-192.png icon-512.png; do
    [ -f "$TMP_REPO/repo/$f" ] && cp "$TMP_REPO/repo/$f" "$APP/static/$f"
done
rm -rf "$TMP_REPO"
echo "    PWA-Dateien kopiert."

# Schritt 4: Python venv + Pakete
echo "[4/8] Python venv einrichten..."
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --quiet flask gunicorn bcrypt
"$APP/venv/bin/pip" freeze > "$APP/requirements.txt"

# Schritt 5: .env anlegen (interaktiv)
echo "[5/8] .env konfigurieren..."
if [ ! -f "$APP/.env" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo ""
    echo "  Einladungscode für Registrierung eingeben (leer lassen = offen):"
    read -rp "  INVITE_CODE: " INVITE
    cat > "$APP/.env" << ENVEOF
SECRET_KEY=$SECRET
INVITE_CODE=$INVITE
ENVEOF
    chmod 600 "$APP/.env"
    echo "  .env erstellt (SECRET_KEY automatisch generiert)."
else
    echo "  .env bereits vorhanden – übersprungen."
fi

# Schritt 6: Datenbank initialisieren
echo "[6/8] Datenbank initialisieren..."
"$APP/venv/bin/python" "$APP/setup_db.py"

# Schritt 7: systemd-Service installieren
echo "[7/8] systemd-Service installieren..."
sudo cp "$SCRIPT_DIR/90tc.service" /etc/systemd/system/90tc.service
sudo systemctl daemon-reload
sudo systemctl enable 90tc.service
sudo systemctl start 90tc.service

# Schritt 8: Testen
echo "[8/8] Service-Test..."
sleep 2
STATUS=$(sudo systemctl is-active 90tc.service)
if [ "$STATUS" = "active" ]; then
    echo "  ✓ 90tc.service läuft"
    CURL=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/api/me)
    if [ "$CURL" = "401" ]; then
        echo "  ✓ API antwortet (HTTP 401 = korrekt, nicht angemeldet)"
    else
        echo "  ! API-Test: HTTP $CURL (erwartet: 401)"
    fi
else
    echo "  ✗ 90tc.service nicht aktiv — Logs:"
    sudo journalctl -u 90tc.service -n 20 --no-pager
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Installation abgeschlossen!"
echo " Nächste Schritte:"
echo " 1. config.yml des Tunnels anpassen (Phase 2)"
echo " 2. CNAME in Cloudflare setzen (Phase 1)"
echo " 3. curl https://challenge.blue-bulls-flechtorf.de/api/me"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
