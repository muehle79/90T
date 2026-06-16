#!/bin/bash
# Nachträglich PUSH_TRIGGER_SECRET setzen und Cron-Job aktualisieren
set -e
APP=/home/pi/90tc-app

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 90TC Push-Secret Fix"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. PUSH_TRIGGER_SECRET in .env nachtragen (falls fehlend)
echo "[1/3] PUSH_TRIGGER_SECRET prüfen..."
if grep -q "PUSH_TRIGGER_SECRET" "$APP/.env" 2>/dev/null; then
    echo "  – bereits vorhanden"
else
    PUSH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    echo "PUSH_TRIGGER_SECRET=$PUSH_SECRET" >> "$APP/.env"
    echo "  ✓ PUSH_TRIGGER_SECRET hinzugefügt"
fi

# 2. Cron-Job mit korrektem Secret aktualisieren
echo "[2/3] Cron-Job aktualisieren..."
PUSH_SECRET=$(grep PUSH_TRIGGER_SECRET "$APP/.env" | tail -1 | cut -d= -f2)
(crontab -l 2>/dev/null | grep -v 'push/trigger'; echo "* * * * * curl -sf -X POST http://127.0.0.1:8080/api/push/trigger -H 'X-Push-Secret: $PUSH_SECRET' > /dev/null 2>&1") | crontab -
echo "  ✓ Cron-Job aktualisiert"

# 3. Service neu starten und Trigger testen
echo "[3/3] Service neu starten und testen..."
sudo systemctl restart 90tc.service
sleep 3
RESULT=$(curl -s -X POST http://127.0.0.1:8080/api/push/trigger -H "X-Push-Secret: $PUSH_SECRET")
if echo "$RESULT" | grep -q '"ok":true'; then
    echo "  ✓ Trigger antwortet: $RESULT"
else
    echo "  ✗ Unerwartete Antwort: $RESULT"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Fertig!"
echo " Cron läuft jede Minute."
echo " Zur konfigurierten Uhrzeit wird der"
echo " Push automatisch gesendet."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
