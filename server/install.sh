#!/bin/bash
# 90TC Install-Skript für Raspberry Pi (Debian 12)
# Aufruf: bash install.sh
set -e

APP=/home/pi/90tc-app
REPO="https://github.com/muehle79/90T.git"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Install-Skript"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Schritt 1: Verzeichnisstruktur
echo "[1/9] Verzeichnisse anlegen..."
mkdir -p "$APP"/{db,static,backups}

# Schritt 2: App-Dateien kopieren (vom Script-Verzeichnis)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[2/9] App-Dateien kopieren..."
cp "$SCRIPT_DIR/app.py"       "$APP/app.py"
cp "$SCRIPT_DIR/setup_db.py"  "$APP/setup_db.py"

# Schritt 3: Statische PWA-Dateien vom GitHub-Repo holen
echo "[3/9] PWA-Dateien vom GitHub-Repo laden..."
TMP_REPO=$(mktemp -d)
git clone --depth=1 "$REPO" "$TMP_REPO/repo" 2>&1 | tail -1
for f in index.html sw.js manifest.json import.html export.html icon-192.png icon-512.png favicon.png; do
    [ -f "$TMP_REPO/repo/$f" ] && cp "$TMP_REPO/repo/$f" "$APP/static/$f"
done
rm -rf "$TMP_REPO"
echo "    PWA-Dateien kopiert."

# Schritt 4: Python venv + Pakete
echo "[4/9] Python venv einrichten..."
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --quiet flask gunicorn bcrypt pywebpush anthropic
"$APP/venv/bin/pip" freeze > "$APP/requirements.txt"

# Schritt 5: .env anlegen (interaktiv)
echo "[5/9] .env konfigurieren..."
if [ ! -f "$APP/.env" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    PUSH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    echo ""
    echo "  Einladungscode für Registrierung eingeben (leer lassen = offen):"
    read -rp "  INVITE_CODE: " INVITE
    echo "  E-Mail-Adresse für VAPID-Pflichtfeld (z.B. lars@example.de):"
    read -rp "  VAPID_CLAIMS_EMAIL: " VAPID_EMAIL
    cat > "$APP/.env" << ENVEOF
SECRET_KEY=$SECRET
INVITE_CODE=$INVITE
VAPID_PRIVATE_PEM=$APP/vapid_private.pem
VAPID_PUBLIC_KEY=WIRD_GLEICH_GESETZT
VAPID_CLAIMS_EMAIL=mailto:$VAPID_EMAIL
PUSH_TRIGGER_SECRET=$PUSH_SECRET
ENVEOF
    chmod 600 "$APP/.env"
    echo "  .env erstellt."
else
    echo "  .env bereits vorhanden – übersprungen."
fi

# Schritt 6: VAPID-Schlüssel generieren
echo "[6/9] VAPID-Schlüssel generieren..."
if [ ! -f "$APP/vapid_private.pem" ]; then
    "$APP/venv/bin/python3" << PYEOF
from py_vapid import Vapid
import base64, os
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
app = '$APP'
v = Vapid()
v.generate_keys()
with open(app + '/vapid_private.pem', 'wb') as f:
    f.write(v.private_pem())
os.chmod(app + '/vapid_private.pem', 0o600)
pub = base64.urlsafe_b64encode(
    v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
).rstrip(b'=').decode()
with open(app + '/.env', 'r') as f:
    content = f.read()
content = content.replace('VAPID_PUBLIC_KEY=WIRD_GLEICH_GESETZT', 'VAPID_PUBLIC_KEY=' + pub)
with open(app + '/.env', 'w') as f:
    f.write(content)
print('  VAPID Public Key:', pub[:20] + '...')
PYEOF
    echo "  VAPID-Schlüssel generiert und in .env eingetragen."
else
    echo "  VAPID-Schlüssel bereits vorhanden – übersprungen."
fi

# Schritt 7: Datenbank initialisieren
echo "[7/9] Datenbank initialisieren..."
"$APP/venv/bin/python" "$APP/setup_db.py"

# Schritt 8: systemd-Service installieren
echo "[8/9] systemd-Service installieren..."
sudo cp "$SCRIPT_DIR/90tc.service" /etc/systemd/system/90tc.service
sudo systemctl daemon-reload
sudo systemctl enable 90tc.service
sudo systemctl start 90tc.service

# Schritt 8b: Cron-Job für Push-Erinnerungen
echo "  Cron-Job für Push-Trigger einrichten..."
PUSH_SECRET=$(grep PUSH_TRIGGER_SECRET "$APP/.env" | cut -d= -f2)
CRON_LINE="* * * * * curl -sf -X POST http://127.0.0.1:8080/api/push/trigger -H 'X-Push-Secret: $PUSH_SECRET' > /dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v 'push/trigger' ; echo "$CRON_LINE" ) | crontab -
echo "  Cron-Job eingerichtet (jede Minute)."

# Schritt 9: Testen
echo "[9/9] Service-Test..."
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
