# Blue Bulls Flechtorf – Administrator-Dokumentation IST-Stand

**Stand:** 11.06.2026  
**System:** Raspberry Pi 4 Model B  
**Projekt:** Darts-Webseite / Darts-Pyramide / Liga-Webportal  
**Domain:** `blue-bulls-flechtorf.de`  
**Zweck:** Vollständige IST-Dokumentation der aktuell betriebenen Infrastruktur.

---

# 1. Kurzfassung

Die Webseite `www.blue-bulls-flechtorf.de` läuft produktiv auf einem Raspberry Pi 4 Model B im Heimnetz.  
Die Veröffentlichung ins Internet erfolgt wegen DS-Lite nicht über klassische IPv4-Portweiterleitung, sondern über Cloudflare Tunnel.

Aktueller Kernaufbau:

```text
Besucher / Browser
        ↓
Cloudflare DNS / Proxy / HTTPS
        ↓
Cloudflare Tunnel
        ↓
cloudflared auf Raspberry Pi
        ↓
Gunicorn Port 8000
        ↓
Flask-App
        ↓
SQLite-Datenbank
```

Wichtige Punkte:

- Debian 12 Bookworm
- Raspberry Pi 4 Model B
- Flask-App in `/home/pi/dart-pyramide`
- Gunicorn läuft als systemd-Service
- Cloudflared läuft als systemd-Service
- Cloudflare DNS ist aktiv
- Strato bleibt Domainregistrar und Mailanbieter
- E-Mail-Versand und Empfang funktionieren
- SPF ist eingerichtet
- DKIM ist eingerichtet
- DMARC fehlt aktuell noch
- Backup-Skripte existieren
- Git ist im Produktivverzeichnis aktuell nicht initialisiert

---

# 2. Hardware

## Server

```text
Raspberry Pi 4 Model B
```

## Router

```text
FRITZ!Box 7590
FRITZ!OS 8.02
```

## Internetanschluss

```text
Deutsche Glasfaser
DS-Lite
```

## Bedeutung von DS-Lite

DS-Lite bedeutet, dass am Anschluss keine echte öffentliche IPv4-Adresse für eingehende Verbindungen zur Verfügung steht.

Konsequenz:

- Klassische IPv4-Portweiterleitung funktioniert nicht zuverlässig.
- MyFRITZ!-Freigaben helfen dafür nur begrenzt.
- Direkter Zugriff von außen über IPv4 ist nicht sauber nutzbar.
- Cloudflare Tunnel ist die richtige Lösung für diesen Anschluss.

---

# 3. Betriebssystem

```text
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
VERSION="12 (bookworm)"
VERSION_CODENAME=bookworm
ID=debian
```

---

# 4. Netzwerk

## Hostname

```text
dartsserver
```

## LAN-Schnittstelle eth0

```text
IPv4-Adresse:
192.168.178.144/24

MAC-Adresse:
dc:a6:32:3a:cc:35

Gateway:
192.168.178.1
```

## IPv6-Adressen eth0

```text
2a00:6020:4a86:d700:e950:a09c:d100:3c8d/128
2a00:6020:4a86:d700:66ec:91d9:1b95:29d0/64
fdcf:3181:6f4a:0:92b4:2918:ca2c:97e5/64
fe80::e950:a09c:d100:3c8d/64
```

## WLAN-Schnittstelle wlan0

```text
IPv4-Adresse:
10.42.0.1/24

MAC-Adresse:
dc:a6:32:3a:cc:36
```

Die Adresse `10.42.0.1/24` deutet auf einen eingerichteten lokalen WLAN-/Hotspot-Betrieb hin.

## Routing

```text
default via 192.168.178.1 dev eth0 proto dhcp src 192.168.178.144 metric 100
10.42.0.0/24 dev wlan0 proto kernel scope link src 10.42.0.1 metric 600
192.168.178.0/24 dev eth0 proto kernel scope link src 192.168.178.144 metric 100
```

---

# 5. FRITZ!Box-Konfiguration

## Gerät

```text
dartsserver
```

## IPv4-Adresse

```text
192.168.178.144
```

## DHCP-Reservierung

Aktiv:

```text
IPv4-Adresse dauerhaft zuweisen
```

Das ist korrekt und wichtig, damit der Raspberry Pi dauerhaft unter derselben lokalen Adresse erreichbar bleibt.

## MAC-Adresse

```text
DC:A6:32:3A:CC:35
```

## Portfreigaben

Vorhanden:

```text
HTTP-Server TCP IPv4
Port am Gerät: 80
Port extern: 80
```

```text
HTTP-Server TCP IPv6
Port am Gerät: 80
Port extern: 80
```

## MyFRITZ!-Freigabe

```text
http://maxvvnqc50ygqwof.myfritz.net:80
```

## Bewertung

Für den produktiven Betrieb über Cloudflare Tunnel sind diese Portfreigaben nicht zwingend nötig.

Sie sind historisch aus der ersten Einrichtungsphase vorhanden.

Da DS-Lite genutzt wird, ist Cloudflare Tunnel der zuverlässige Veröffentlichungsweg.

---

# 6. Domain und STRATO

## Domain

```text
blue-bulls-flechtorf.de
```

## Registrar

```text
STRATO
```

## STRATO Nameserver-Einstellung

Bei STRATO sind eigene Nameserver aktiviert.

```text
Nameserver 1:
valentin.ns.cloudflare.com

Nameserver 2:
ximena.ns.cloudflare.com
```

## STRATO-Hinweis

STRATO zeigt sinngemäß:

```text
Bei der Verwendung eigener Nameserver stehen STRATO E-Mail-Funktionen für diese Domain nicht zur Verfügung.
```

Praktische Bedeutung:

- STRATO verwaltet DNS nicht mehr aktiv.
- DNS muss vollständig bei Cloudflare gepflegt werden.
- E-Mail funktioniert trotzdem, wenn die STRATO-Mail-DNS-Einträge korrekt in Cloudflare vorhanden sind.

---

# 7. Cloudflare DNS

## Cloudflare-Tarif

```text
Free Plan
```

## Nameserver

```text
valentin.ns.cloudflare.com
ximena.ns.cloudflare.com
```

## Zone-Export

Die Cloudflare-Zone wurde exportiert:

```text
blue-bulls-flechtorf.de.txt
```

Export-Zeitpunkt laut Datei:

```text
2026-06-11 17:04:11
```

---

# 8. Cloudflare DNS-Einträge

## SOA

```text
blue-bulls-flechtorf.de 3600 IN SOA valentin.ns.cloudflare.com. dns.cloudflare.com.
```

## NS Records

```text
blue-bulls-flechtorf.de. 86400 IN NS valentin.ns.cloudflare.com.
blue-bulls-flechtorf.de. 86400 IN NS ximena.ns.cloudflare.com.
```

## A Record

```text
Name:
blue-bulls-flechtorf.de

Typ:
A

Wert:
94.31.118.64

Proxy:
aktiv

TTL:
Auto / 1 laut Export
```

## AAAA Record

```text
Name:
blue-bulls-flechtorf.de

Typ:
AAAA

Wert:
2a00:6020:4a86:d700:e950:a09c:d100:3c8d

Proxy:
aktiv

TTL:
Auto / 1 laut Export
```

## CNAME autoconfig

```text
Name:
autoconfig.blue-bulls-flechtorf.de

Typ:
CNAME

Ziel:
autoconfigure.strato.de

Proxy:
aktiv
```

## CNAME www

```text
Name:
www.blue-bulls-flechtorf.de

Typ:
CNAME

Ziel:
3a2878de-1b4a-45b3-9383-865a4a6dee03.cfargotunnel.com

Proxy:
aktiv
```

Dieser Eintrag ist der zentrale Tunnel-Eintrag für die Webseite unter:

```text
www.blue-bulls-flechtorf.de
```

## DKIM CNAME Records

```text
strato-dkim-0001._domainkey.blue-bulls-flechtorf.de
→ strato-dkim-0001._domainkey.strato.de

strato-dkim-0002._domainkey.blue-bulls-flechtorf.de
→ strato-dkim-0002._domainkey.strato.de

strato-dkim-0003._domainkey.blue-bulls-flechtorf.de
→ strato-dkim-0003._domainkey.strato.de
```

Proxy:

```text
Nur DNS
```

Bewertung:

DKIM ist vorhanden und korrekt als STRATO-DKIM-CNAME eingerichtet.

## MX Records

```text
*.blue-bulls-flechtorf.de. 1 IN MX 5 smtpin.rzone.de.
blue-bulls-flechtorf.de. 1 IN MX 5 smtpin.rzone.de.
```

Wichtig:

Diese MX-Einträge waren entscheidend für funktionierenden E-Mail-Empfang.

Sie sollten nicht durch `mx00.strato.de`, `mx01.strato.de` oder andere Einträge ersetzt werden.

## SRV Record

```text
_autodiscover._tcp.blue-bulls-flechtorf.de
0 100 443 autoconfigure.strato.de.
```

## SPF TXT Record

```text
blue-bulls-flechtorf.de. 3600 IN TXT "v=spf1 include:spf.strato.de -all"
```

Bewertung:

SPF ist korrekt gesetzt.

## Domainkey TXT Record

```text
_domainkey.blue-bulls-flechtorf.de. 1 IN TXT "o=~; t=y; r=dkim@rzone.de"
```

## DMARC

Aktueller Test:

```bash
dig TXT _dmarc.blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
keine Ausgabe
```

Bewertung:

DMARC ist aktuell nicht eingerichtet.

---

# 9. Aktuelle externe DNS-Auflösung

## A

```bash
dig A blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
172.67.171.28
104.21.55.110
```

Das sind Cloudflare-Proxy-IP-Adressen.

## AAAA

```bash
dig AAAA blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
2606:4700:3031::6815:376e
2606:4700:3037::ac43:ab1c
```

Das sind Cloudflare-Proxy-IPv6-Adressen.

## CNAME www

```bash
dig CNAME www.blue-bulls-flechtorf.de +short
```

Kein direkter Wert sichtbar, weil der Record proxied ist.

## MX

```bash
dig MX blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
5 smtpin.rzone.de.
```

## TXT / SPF

```bash
dig TXT blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
"v=spf1 include:spf.strato.de -all"
```

## DKIM

```bash
dig CNAME strato-dkim-0001._domainkey.blue-bulls-flechtorf.de +short
dig CNAME strato-dkim-0002._domainkey.blue-bulls-flechtorf.de +short
dig CNAME strato-dkim-0003._domainkey.blue-bulls-flechtorf.de +short
```

Ergebnis:

```text
strato-dkim-0001._domainkey.strato.de.
strato-dkim-0002._domainkey.strato.de.
strato-dkim-0003._domainkey.strato.de.
```

---

# 10. Cloudflare SSL/TLS

## Verschlüsselungsmodus

Cloudflare zeigt:

```text
Aktueller Verschlüsselungsmodus:
Vollständig
```

Das entspricht Cloudflare-Modus "Full".

## Universal Certificate

Vorhanden:

```text
Hosts:
*.blue-bulls-flechtorf.de
blue-bulls-flechtorf.de

Typ:
Universal

Status:
Aktiv

Läuft ab:
2026-09-09
```

## Backup Certificate

Vorhanden:

```text
Hosts:
*.blue-bulls-flechtorf.de
blue-bulls-flechtorf.de

Typ:
Backup

Status:
Sicherung ausgegeben

Läuft ab:
2026-07-14
```

## Bewertung

HTTPS für Besucher wird durch Cloudflare bereitgestellt.

Lokales Let's Encrypt wurde nicht verwendet.

Grund:

- HTTP-Challenge scheiterte wegen Cloudflare/DS-Lite/Tunnel-Situation.
- Cloudflare übernimmt die TLS-Terminierung zuverlässig.

---

# 11. Cloudflare Tunnel

## Tunnelname

```text
darts-tunnel
```

## Tunnel-ID

```text
3a2878de-1b4a-45b3-9383-865a4a6dee03
```

## Erstellt

```text
2025-06-22 06:55:31.485694 +0000 UTC
```

## Connector ID

```text
1d3b0771-6004-4739-9d7a-bc72bb16c686
```

## Connector erstellt

```text
2026-01-22T21:06:45Z
```

## Architektur

```text
linux_arm
```

## Cloudflared-Version

```text
2025.6.1
```

## Origin IP laut cloudflared tunnel info

```text
94.31.118.29
```

## Edge-Verbindungen

```text
1xfra03
1xfra08
1xfra13
1xfra14
```

## Hinweis

Cloudflared meldet:

```text
Your version 2025.6.1 is outdated.
We recommend upgrading it to 2026.6.0
```

---

# 12. Cloudflared-Service

## Datei

```text
/etc/systemd/system/cloudflared.service
```

## Inhalt

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/local/bin/cloudflared tunnel run darts-tunnel
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

## Status

```text
active (running)
```

## Laufzeit

```text
seit Thu 2026-01-22 22:06:28 CET
```

## Prüfung

```bash
sudo systemctl status cloudflared --no-pager
```

## Logs

```bash
journalctl -u cloudflared -f
```

Gesuchter Erfolgsindikator:

```text
Registered tunnel connection
```

---

# 13. Cloudflared-Konfiguration

## Datei

```text
/home/pi/.cloudflared/config.yml
```

## Inhalt

```yaml
tunnel: darts-tunnel
credentials-file: ~/.cloudflared/3a2878de-1b4a-45b3-9383-865a4a6dee03.json

ingress:
  - hostname: www.blue-bulls-flechtorf.de
    service: http://localhost:8000
  - service: http_status:404
```

## Interpretation

Aktuell wird nur folgender Host über den Tunnel bedient:

```text
www.blue-bulls-flechtorf.de
```

Ziel:

```text
http://localhost:8000
```

Das bedeutet:

Cloudflare Tunnel leitet direkt an Gunicorn weiter.

Nginx ist lokal aktiv, wird von diesem Tunnelpfad aber nicht zwingend genutzt.

Wenn der Tunnel bewusst über Nginx laufen soll, müsste der Service geändert werden auf:

```yaml
service: http://localhost:80
```

Aktuell funktioniert der Betrieb trotzdem sauber.

---

# 14. Cloudflared-Dateien

Verzeichnis:

```text
/home/pi/.cloudflared/
```

Inhalt:

```text
3a2878de-1b4a-45b3-9383-865a4a6dee03.json
cert.pem
config.yml
```

Rechte:

```text
drwx------  /home/pi/.cloudflared
-r--------  3a2878de-1b4a-45b3-9383-865a4a6dee03.json
-rw-------  cert.pem
-rw-r--r--  config.yml
```

Bewertung:

Die Tunnel-Credentials-Datei ist restriktiv geschützt. Das ist gut.

---

# 15. Webanwendung

## Projektverzeichnis

```text
/home/pi/dart-pyramide
```

## Technologie

```text
Python / Flask
Gunicorn
SQLite
HTML Templates
Static Files
```

## Datenbank

```text
SQLite
```

## Aktuelle Datenbankdatei

```text
/home/pi/dart-pyramide/db/pyramide.db
```

Dateigröße:

```text
132K
```

## Tabellen

```text
benutzer
einstellungen
liga_einstellungen
liga_einstellungen_alt
liga_saison_teilnehmer
liga_saisons
liga_spiele
liga_spiele_korrekturen
regeln
```

---

# 16. Projektstruktur

## Dateien Ebene maxdepth 2

```text
./app.py
./check_tables.py
./db/pyramide_backup_20260105_215721.db
./db/pyramide_backup_20260105_215822.db
./db/pyramide_backup_20260106_154538.db
./db/pyramide_backup_20260107_220325.db
./db/pyramide.db
./db/pyramide.db.bak_20260105_192740
./.env
./__pycache__/app.cpython-311.pyc
./reset_liga.sh
./setup_db.py
./static/logo.png
./static/manifest.json
./templates/admin_debug_fairness.html
./templates/base.html
./templates/benutzerfreigabe.html
./templates/benutzer.html
./templates/einstellungen.html
./templates/einstellungen.html.bak_20260105_192740
./templates/fehler.html
./templates/forderung.html
./templates/historie.html
./templates/impressum.html
./templates/index.html
./templates/liga_einstellungen.html
./templates/liga_korrektur_log.html
./templates/liga_saison.html
./templates/liga_saison.html.bak_20260105_192740
./templates/liga_spiele.html
./templates/liga_spieltage.html
./templates/login.html
./templates/passwort_reset.html
./templates/passwort_vergessen.html
./templates/portal.html
./templates/profil.html
./templates/rangliste.html
./templates/regeln_aendern.html
./templates/regeln.html
./templates/registrieren.html
./templates/spieler.html
./templates/ueber_uns.html
./venv/pyvenv.cfg
```

## Verzeichnisse Ebene maxdepth 2

```text
.
./db
./__pycache__
./static
./static/css
./static/img
./templates
./venv
./venv/bin
./venv/include
./venv/lib
```

---

# 17. Environment-Datei

## Datei

```text
/home/pi/dart-pyramide/.env
```

## Enthaltene Variablen

```text
MAIL_PASSWORD=***GEHEIM***
SECRET_KEY=***GEHEIM***
```

Bewertung:

Gut: sensible Werte liegen nicht direkt in der systemd-Datei.

Wichtig:

- `.env` darf nicht öffentlich gespeichert werden.
- `.env` darf nicht in Git veröffentlicht werden.
- Datei sollte restriktive Rechte haben, z. B. `chmod 600 .env`.

---

# 18. Gunicorn / Flask-Service

## Datei

```text
/etc/systemd/system/flaskapp.service
```

## Inhalt

```ini
[Unit]
Description=Flask Web Application
After=network.target

[Service]
User=root
WorkingDirectory=/home/pi/dart-pyramide
EnvironmentFile=/home/pi/dart-pyramide/.env
Environment="PATH=/home/pi/dart-pyramide/venv/bin"
ExecStart=/home/pi/dart-pyramide/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app

[Install]
WantedBy=multi-user.target
```

## Status

```text
active (running)
```

## Laufzeit

```text
seit Thu 2026-01-22 22:06:21 CET
```

## Prozess

```text
gunicorn
```

## Worker

```text
4 Worker
```

## Port

```text
8000
```

## Wichtige Warnung

Systemd meldet:

```text
Warning: The unit file, source configuration file or drop-ins of flaskapp.service changed on disk.
Run 'systemctl daemon-reload' to reload units.
```

Das bedeutet:

Die Service-Datei wurde geändert, aber systemd wurde danach nicht neu geladen.

Empfohlener Befehl:

```bash
sudo systemctl daemon-reload
```

Danach:

```bash
sudo systemctl restart flaskapp.service
```

Nicht blind während eines kritischen Betriebsfensters machen, sondern bewusst.

## Bewertung

Die Anwendung läuft, aber aktuell als:

```text
User=root
```

Das funktioniert, ist aber aus Sicherheitsgründen nicht optimal.

Empfehlung:

Später auf einen unprivilegierten Benutzer umstellen, z. B. `pi` oder einen eigenen Service-User.

---

# 19. Nginx

## Aktive Site

```text
/etc/nginx/sites-enabled/dart-pyramide
→ /etc/nginx/sites-available/dart-pyramide
```

## Verfügbare Sites

```text
/etc/nginx/sites-available/dart-pyramide
/etc/nginx/sites-available/default
```

## Aktive Konfiguration

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Nginx-Test

```text
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

## Status

```text
active (running)
```

## Laufzeit

```text
seit Thu 2026-01-22 22:06:26 CET
```

## Bewertung

Nginx ist korrekt eingerichtet und funktionsfähig.

Aktuell verwendet der Cloudflare Tunnel jedoch direkt:

```text
http://localhost:8000
```

Damit wird Nginx durch den Tunnel aktuell nicht genutzt.

Das ist kein akuter Fehler, aber architektonisch sollte später entschieden werden:

Variante A:

```text
Cloudflare Tunnel → Gunicorn direkt
```

oder

Variante B:

```text
Cloudflare Tunnel → Nginx → Gunicorn
```

Für saubere Trennung wäre Variante B oft besser.

---

# 20. Backup-Situation

## Gefundene Backup-Dateien

```text
/home/pi/backup.sh
/home/pi/backup_db.sh
/home/pi/backup_db.log
/home/pi/dart-pyramide/db/pyramide_backup_20260105_215822.db
/home/pi/dart-pyramide/db/pyramide_backup_20260107_220325.db
/home/pi/dart-pyramide/db/pyramide_backup_20260105_215721.db
/home/pi/dart-pyramide/db/pyramide_backup_20260106_154538.db
```

## Cronjobs

```cron
*/10 * * * * /home/pi/cloudflare_ddns.sh >> /home/pi/cloudflare_ddns.log 2>&1
15 3 * * 0 sudo /home/pi/backup_db.sh >> /home/pi/backup_db.log 2>&1
0 2 1 * * sudo ./backup.sh
0 2 15 * * sudo ./backup.sh
```

## Bewertung

Es existieren Backup-Skripte und Datenbank-Backups.

Unklar ist aktuell:

- wohin `backup.sh` sichert
- wohin `backup_db.sh` sichert
- ob die Backups regelmäßig geprüft werden
- ob Wiederherstellung getestet wurde

Das ist ein wichtiger offener Punkt.

---

# 21. Cloudflare DDNS

## Cronjob

```cron
*/10 * * * * /home/pi/cloudflare_ddns.sh >> /home/pi/cloudflare_ddns.log 2>&1
```

## Bewertung

Es gibt ein Cloudflare-DDNS-Skript.

Da die Webseite über Cloudflare Tunnel läuft, ist zu prüfen, ob dieses Skript für den Webbetrieb noch notwendig ist.

Es kann weiterhin für den A-Record der Root-Domain relevant sein.

---

# 22. Git / Versionsverwaltung

Im Produktivverzeichnis:

```bash
cd /home/pi/dart-pyramide
git status
```

Ergebnis:

```text
fatal: not a git repository
```

Bewertung:

Das Produktivverzeichnis ist aktuell kein Git-Repository.

Das bedeutet:

- Änderungen am Produktivsystem sind lokal nicht versioniert.
- Rückverfolgung von Änderungen ist erschwert.
- Rollback ist schwieriger.

Empfehlung:

Produktivdeployment mittelfristig über Git/Gitea strukturieren.

---

# 23. Mail-System

## Anbieter

```text
STRATO
```

## DNS-Verwaltung

```text
Cloudflare
```

## Empfang

Funktioniert.

## Versand

Funktioniert.

## Wichtige Erkenntnis aus der Fehleranalyse

Nach der Nameserver-Umstellung zu Cloudflare funktionierten E-Mails nur dann korrekt, als:

- die von Cloudflare übernommenen STRATO-MX-Einträge beibehalten wurden
- der SPF-TXT-Eintrag korrekt gesetzt wurde

## MX

```text
5 smtpin.rzone.de.
```

## SPF

```text
v=spf1 include:spf.strato.de -all
```

## DKIM

```text
strato-dkim-0001._domainkey.strato.de.
strato-dkim-0002._domainkey.strato.de.
strato-dkim-0003._domainkey.strato.de.
```

## DMARC

Nicht vorhanden.

Empfehlung:

```text
Name:
_dmarc

Typ:
TXT

Wert:
v=DMARC1; p=none
```

---

# 24. Typische Fehler und Diagnose

## Fehler: Cloudflare 502 Bad Gateway

Bedeutung:

Cloudflare erreicht den Ursprung nicht sauber.

Prüfen:

```bash
sudo systemctl status cloudflared --no-pager
sudo systemctl status flaskapp.service --no-pager
curl http://localhost:8000
```

## Fehler: Cloudflare 503 Service Unavailable

Mögliche Ursache:

Tunnel-Konfiguration falsch oder Dienstziel nicht erreichbar.

Prüfen:

```bash
cat /home/pi/.cloudflared/config.yml
journalctl -u cloudflared -f
```

## Fehler: Nginx Welcome Page

Ursache:

Nginx Default-Site aktiv oder falsche Site aktiv.

Prüfen:

```bash
ls -l /etc/nginx/sites-enabled/
sudo nginx -t
```

## Fehler: Webseite lokal nicht erreichbar

Prüfen:

```bash
curl http://localhost:8000
sudo systemctl status flaskapp.service --no-pager
```

## Fehler: E-Mail Empfang geht nicht

Prüfen:

```bash
dig MX blue-bulls-flechtorf.de +short
```

Erwartung:

```text
5 smtpin.rzone.de.
```

## Fehler: E-Mail Versand geht nicht

Prüfen:

```bash
dig TXT blue-bulls-flechtorf.de +short
```

Erwartung:

```text
"v=spf1 include:spf.strato.de -all"
```

---

# 25. Wiederanlauf nach Neustart

Nach Neustart sollten folgende Dienste automatisch laufen:

```bash
sudo systemctl status flaskapp.service --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status cloudflared --no-pager
```

Falls nicht:

```bash
sudo systemctl restart flaskapp.service
sudo systemctl restart nginx
sudo systemctl restart cloudflared
```

---

# 26. Minimaler Wiederherstellungsplan

Wenn ein neuer Raspberry Pi aufgebaut werden muss:

1. Debian 12 installieren
2. Benutzer `pi` einrichten
3. Netzwerk verbinden
4. Projekt nach `/home/pi/dart-pyramide` kopieren
5. Python venv erstellen
6. Abhängigkeiten installieren
7. `.env` wiederherstellen
8. SQLite-Datenbank wiederherstellen
9. `flaskapp.service` einrichten
10. Nginx installieren
11. Nginx-Site `dart-pyramide` einrichten
12. cloudflared installieren
13. `.cloudflared`-Credentials wiederherstellen
14. `cloudflared.service` einrichten
15. Dienste starten
16. Webseite testen

---

# 27. Offene Punkte / To-do-Liste

## Hoch

### 1. DMARC einrichten

Aktuell fehlt DMARC.

Empfohlener Startwert:

```text
v=DMARC1; p=none
```

### 2. Backup-Skripte dokumentieren

Aktuell existieren:

```text
/home/pi/backup.sh
/home/pi/backup_db.sh
```

Aber deren Inhalt und Ziel sind in dieser Dokumentation noch nicht enthalten.

### 3. Wiederherstellung testen

Ein Backup ist erst dann belastbar, wenn eine Wiederherstellung erfolgreich getestet wurde.

### 4. systemctl daemon-reload ausführen

Systemd meldet, dass die `flaskapp.service`-Datei geändert wurde.

Empfohlen:

```bash
sudo systemctl daemon-reload
```

Danach kontrolliert neu starten.

## Mittel

### 5. Gunicorn nicht mehr als root ausführen

Aktuell:

```text
User=root
```

Empfohlen:

```text
User=pi
```

oder ein eigener Service-Benutzer.

### 6. cloudflared aktualisieren

Aktuell:

```text
2025.6.1
```

Empfohlen laut cloudflared:

```text
2026.6.0
```

### 7. Architekturentscheidung Tunnelziel

Aktuell:

```text
Cloudflare Tunnel → Gunicorn direkt
```

Mögliche sauberere Variante:

```text
Cloudflare Tunnel → Nginx → Gunicorn
```

### 8. Nginx server_name konkretisieren

Aktuell:

```text
server_name _;
```

Empfohlen:

```text
server_name blue-bulls-flechtorf.de www.blue-bulls-flechtorf.de;
```

### 9. Git-Versionierung einführen

Produktivverzeichnis ist aktuell kein Git-Repository.

## Niedrig

### 10. A-/AAAA-Record prüfen

Da `www` über den Tunnel läuft, sollte geprüft werden, ob A/AAAA für die Root-Domain weiterhin sinnvoll sind.

### 11. Root-Domain-Verhalten vereinheitlichen

Aktuell ist der Tunnel explizit nur für `www.blue-bulls-flechtorf.de` konfiguriert.

Es sollte entschieden werden:

- Root-Domain auch über Tunnel
- oder Root-Domain per Redirect auf www

### 12. Dokumentation regelmäßig aktualisieren

Bei Änderungen an:

- DNS
- Tunnel
- Services
- Backup
- Datenbank
- Deployment

sollte diese Dokumentation angepasst werden.

---

# 28. Fazit

Der aktuelle Server ist produktiv funktionsfähig.

Webseite:

- erreichbar
- HTTPS aktiv
- Cloudflare Tunnel aktiv

E-Mail:

- Versand funktioniert
- Empfang funktioniert
- SPF korrekt
- DKIM korrekt
- DMARC fehlt

System:

- Flask/Gunicorn läuft
- Nginx läuft
- Cloudflared läuft
- SQLite-Datenbank vorhanden
- Backup-Skripte vorhanden

Die wichtigsten nächsten Schritte sind:

1. DMARC ergänzen
2. Backup-Skripte vollständig dokumentieren
3. Restore testen
4. cloudflared aktualisieren
5. Gunicorn nicht mehr als root betreiben
6. Root-Domain und www sauber vereinheitlichen
