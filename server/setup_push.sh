#!/bin/bash
# Einmalige Push-Einrichtung für bestehende 90TC-Installs
set -e
APP=/home/pi/90tc-app

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Push-Einrichtung"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. pywebpush sicherstellen
echo "[1/4] pywebpush installieren..."
"$APP/venv/bin/pip" install --quiet pywebpush
echo "  ✓ pywebpush bereit"

# 2. VAPID-Schlüssel generieren
echo "[2/4] VAPID-Schlüssel generieren..."
if grep -q "VAPID_PUBLIC_KEY" "$APP/.env" 2>/dev/null; then
    echo "  – bereits vorhanden, übersprungen"
else
    "$APP/venv/bin/python3" << PYEOF
import base64, os, secrets
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
app = '/home/pi/90tc-app'
v = Vapid()
v.generate_keys()
with open(app + '/vapid_private.pem', 'wb') as f:
    f.write(v.private_pem())
os.chmod(app + '/vapid_private.pem', 0o600)
pub = base64.urlsafe_b64encode(
    v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
).rstrip(b'=').decode()
push_secret = secrets.token_hex(24)
with open(app + '/.env', 'a') as f:
    f.write('\nVAPID_PRIVATE_PEM=' + app + '/vapid_private.pem\n')
    f.write('VAPID_PUBLIC_KEY=' + pub + '\n')
    f.write('VAPID_CLAIMS_EMAIL=mailto:lars.muehlhaus@gmail.com\n')
    f.write('PUSH_TRIGGER_SECRET=' + push_secret + '\n')
print('  Schluessel generiert')
PYEOF
fi

# 3. Cron-Job einrichten
echo "[3/4] Cron-Job einrichten..."
PUSH_SECRET=$(grep PUSH_TRIGGER_SECRET "$APP/.env" | tail -1 | cut -d= -f2)
CRON_LINE="* * * * * curl -sf -X POST http://127.0.0.1:8080/api/push/trigger -H 'X-Push-Secret: $PUSH_SECRET' > /dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v 'push/trigger'; echo "$CRON_LINE") | crontab -
echo "  ✓ Cron-Job eingerichtet (jede Minute)"

# 4. Service neu starten und testen
echo "[4/4] Service neu starten..."
sudo systemctl restart 90tc.service
sleep 3
RESULT=$(curl -s http://127.0.0.1:8080/api/vapid-key)
if echo "$RESULT" | grep -q "publicKey"; then
    echo "  ✓ Push konfiguriert — API antwortet korrekt"
else
    echo "  ✗ Fehler: $RESULT"
    sudo journalctl -u 90tc.service -n 20 --no-pager
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Fertig! Jetzt in der App:"
echo " Einstellungen → Berechtigung anfragen"
echo " → Haken setzen → Speichern"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
