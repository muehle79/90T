# 90-Tage-Challenge PWA — Projektstatus

**Stand:** 2026-06-16  
**Live-URL (neu):** https://challenge.blue-bulls-flechtorf.de  
**Live-URL (alt/GitHub Pages):** https://muehle79.github.io/90T/ *(Weiterleitungsseite — nicht mehr primär)*  
**Repository:** https://github.com/muehle79/90T (Branch: main)  
**Aktuelle Version:** `1.9.1`  
**Letzter Commit:** `— (noch nicht gepusht)`

---

## Versionshistorie

| Version | Commit | Inhalt |
|---|---|---|
| 1.0.x | `8038f32` | Initiale Builds, URL-Import (iOS Kurzbefehl), Locale-Fix |
| 1.1.0 | `05d6a68` | 4 Bug-Fixes: Foto-Upload, Check-Tage, Kalender-Dots, PWA-Export/Import |
| 1.2.0 | `dc9617a` | 4 Features: Gewichts-Chart, Foto-Vergleich, Export-Reminder, Notifications |
| 1.2.1 | `8b5c4b0` | Hotfix: doppeltes `const cfg` in `renderSettings()` — App startete nicht |
| 1.2.2 | `151a150` + `80c3458` | Hotfix: iOS Notifications via `SW.showNotification()`, App-Versionierung |
| 1.3.0 | `af040a0` | Feat: Makro-basierte Kalorienberechnung & wöchentliche Zielwert-Anpassungen |
| 1.3.1 | `e9683fa` | Feat: Historische Zielwerte (Anpassungen gelten nur für zukünftige Wochen) |
| 1.4.0 | `3ded09d` | Feat: Kalorien-Statistiken (Gesamt-Ø, Wochen-Ø) + Kalorienverlauf-Chart |
| 1.4.1 | `7d6bb9f` | Feat: Ø Kalorien IST im Wochencheck |
| 1.4.2 | `669a512` | Feat: Empirische TDEE-Schätzung |
| 1.4.3 | `e070447` | Feat: Größe (cm) und Geburtsdatum im Profil |
| 1.4.4 | `cf6566f` | Feat: Geschlecht + formelbasierte TDEE (Mifflin-St Jeor) |
| 1.5.0 | `c3badf6` | **Migration:** Auth-Screen, Dirty-Queue-Sync, sw.js v3, manifest.json, server/ |
| 1.5.1 | `4e3ca60` | Fix: async/await Auth-Check in init() — JS-Syntaxfehler behoben |
| 1.5.2 | `8fa4d31` | Fix: screen-auth CSS .active-Selektor + inline-style entfernt |
| 1.5.3 | `36cf6ab` | Fix: _doImport markiert dirty-queue + forceSync Button |
| 1.5.3 | `7ef1690` | Feat: Neues App-Icon "Kinetic Meridian" + favicon & apple-touch-icon |
| 1.6.0 | `fd82f44` | Feat: Changelog-Modal — zeigt Neuerungen nach jedem Versionssprung |
| 1.7.0 | `89093c4` | Feat: sync() bei App-Start + nach jedem Speichern — Geräte immer synchron |
| 1.7.0 | `b706306` | Fix: sw.js Network-First für index.html — kein manueller Cache-Clear mehr nötig |
| 1.7.0 | `48700d3` | Fix: Changelog-Modal auch nach Cache-Clear anzeigen (bestehende Nutzer) |
| 1.7.0 | `3fac75b` | Fix: controllerchange-Listener — PWA lädt automatisch neu wenn neuer SW aktiv |
| 1.7.0 | `207c436` | Fix: checkReminderNotif bei jedem App-Start aufrufen (nicht nur bei URL-Import) |
| 1.7.1 | — | Versionssprung für alle 1.7.0-Fixes — Changelog-Modal + Push-Erinnerung sichtbar |
| 1.9.1 | `—` | Feat: Kalorien-Modus-Toggle — automatisch aus Makros oder manuell eingeben |
| 1.9.0 | `5429233` | Feat: Frei wählbare Challenge-Dauer (90T / eigener Zeitraum / ∞), Tracking fortführen oder beenden, Neue Challenge starten |
| 1.8.0 | `47f03d0` | Feat: Echte Web-Push via VAPID — server-seitig, funktioniert auch wenn App geschlossen |

> **Regel:** Bei jeder Änderung `APP_VERSION` in `index.html` erhöhen + `PROJEKTSTATUS.md` mit committen.

---

## Architektur (aktuell)

```
iPhone/Mac/Browser
    ── HTTPS ──▶ Cloudflare (SSL, Tunnel)
                    ── cloudflared ──▶ Raspberry Pi 4 (dartsserver, Debian 12)
                                          ├── Flask + Gunicorn :8080 (90tc.service)
                                          │     ├── GET /  → static/index.html
                                          │     ├── POST /api/register + /api/login
                                          │     ├── GET /api/me
                                          │     ├── GET /api/sync?since=<ts>
                                          │     └── PUT /api/kv
                                          └── SQLite: /home/pi/90tc-app/db/90tc.db
```

**Subdomain:** `challenge.blue-bulls-flechtorf.de`  
**Tunnel:** `darts-tunnel` (ID: `3a2878de-1b4a-45b3-9383-865a4a6dee03`)  
**Service:** `90tc.service` (User=pi, Gunicorn -w 2 -b 127.0.0.1:8080)  
**Backup:** Cron täglich 03:00 → `/home/pi/90tc-app/backups/90tc-YYYY-MM-DD.db` (30 Tage Aufbewahrung)

---

## Projektbeschreibung

Single-file PWA als persönliches Tagebuch für die 90-Tage-Challenge. Basiert auf dem 90TC_Workbook.pdf (S. 70–180). **Offline-first** — alle Daten primär im `localStorage`, Sync zum eigenen Server über Dirty-Queue (Last-Write-Wins pro Key).

**Dateien im Repo:**

| Datei | Zweck |
|---|---|
| `index.html` | Komplette App — HTML + CSS + JS in einer Datei |
| `manifest.json` | PWA-Manifest (start_url: challenge.blue-bulls-flechtorf.de) |
| `sw.js` | Service Worker v3 — /api/* network-only, static cache-first |
| `icon-192.png` / `icon-512.png` / `favicon.png` | App-Icons (Kinetic Meridian Design, ohne feste Tageszahl) |
| `import.html` | Hilfsseite für URL-basierten Daten-Import (iOS Kurzbefehl) |
| `export.html` | Einmal-Export-Seite ohne Auth (für Migration von alten Daten) |
| `server/app.py` | Flask-Backend: Auth + KV-Sync + Web-Push (VAPID) |
| `server/setup_db.py` | SQLite-Schema-Initialisierung (inkl. push_subscriptions) |
| `server/90tc.service` | systemd-Unit |
| `server/install.sh` | Installations-Skript für Raspberry Pi (inkl. VAPID + Cron) |
| `server/deploy.sh` | Update-Skript: pull → statische Dateien → Backend neu starten |
| `server/setup_push.sh` | Einmalige Push-Einrichtung für bestehende Installs |
| `server/fix_push_secret.sh` | Fix: PUSH_TRIGGER_SECRET nachtragen + Cron-Job aktualisieren |
| `PROJEKTSTATUS.md` | Diese Datei |

---

## Auth & Sync

- **Registrierung:** Invite-Code geschützt (in `/home/pi/90tc-app/.env`)
- **Session:** httpOnly + Secure + SameSite=Lax Cookie, 1 Jahr Laufzeit
- **Passwörter:** bcrypt-Hash
- **Sync-Strategie:** Offline-first, Dirty-Queue in localStorage (`90tc__dirty`), Last-Write-Wins pro Key anhand `updated_at` (Unix-ms)
- **Sync-Aufruf:** App-Start (nach Auth), nach jedem S.set(), bei `online`-Event
- **Multi-Device:** iPhone → Server → Mac (und zurück) ✓

## Web Push

- **Standard:** VAPID (Web Push Protocol) — funktioniert auf iOS 16.4+ als Home-Screen-PWA
- **Schlüssel:** `VAPID_PRIVATE_PEM` (Datei auf Pi) + `VAPID_PUBLIC_KEY` (base64url, in .env)
- **Abonnement:** Browser → `pushManager.subscribe()` → `/api/push/subscribe` → SQLite `push_subscriptions`
- **Versand:** Cron jede Minute → `POST /api/push/trigger` (Secret: `PUSH_TRIGGER_SECRET`) → pywebpush → APNs/FCM
- **Zeitzone:** Europe/Berlin (Pi-Systemzeit), Vergleich mit `settings.reminder.time`
- **Cron prüfen:** `crontab -l | grep push`
- **Manuell testen:** `SECRET=$(grep PUSH_TRIGGER_SECRET /home/pi/90tc-app/.env | tail -1 | cut -d= -f2) && curl -s -X POST http://127.0.0.1:8080/api/push/trigger -H "X-Push-Secret: $SECRET"`

---

## Screens-Übersicht

| Screen-ID | Zweck | Erreichbar via |
|---|---|---|
| `screen-auth` | Login / Registrieren | App-Start ohne gültige Session |
| `screen-splash` | Startscreen / Onboarding | Nach Login ohne Settings |
| `screen-setup` | 3-Schritt-Wizard Ersteinrichtung | Splash |
| `screen-calendar` | Kalender + Statistiken | Nav-Bar |
| `screen-entry` | Tageseintrag | Kalender-Tag, Nav "Heute" |
| `screen-weekly` | Wöchentlicher Check | Entry-Banner an Check-Tagen |
| `screen-monthly` | Monatlicher Check | Entry-Banner an Check-Tagen |
| `screen-final` | Tag-90 Abschlussauswertung | Entry-Banner Tag 90 |
| `screen-statusquo` | Status Quo bearbeiten | Einstellungen |
| `screen-chart` | SVG Gewichtsverlauf-Chart | Kalender → "📊 Fortschritt" |
| `screen-fotocompare` | Vorher/Nachher Vergleich | Abschluss-Screen, Einstellungen |
| `screen-settings` | Einstellungen + Datensicherung | Nav-Bar |

---

## Server-Wartung

```bash
# Service-Status
systemctl status 90tc.service

# Logs
sudo journalctl -u 90tc.service -n 50 --no-pager

# Backup manuell
sqlite3 /home/pi/90tc-app/db/90tc.db ".backup /home/pi/90tc-app/backups/90tc-$(date +%F)-manual.db"

# App-Update (neue Version deployen)
cd /home/pi/90tc-app/static
curl -sL "https://raw.githubusercontent.com/muehle79/90T/main/index.html" -o index.html
curl -sL "https://raw.githubusercontent.com/muehle79/90T/main/sw.js" -o sw.js
```

---

## Lokaler Testserver (Entwicklung)

**Pfad:** `/home/test/90TC_APP`  
**IP:** `192.168.178.110:8080`  
**Starten:** `bash dev.sh` (Vordergrund) oder:

```bash
export $(grep -v '^#' server/.env | xargs) && nohup server/venv/bin/python server/app.py > /tmp/90tc-dev.log 2>&1 & echo $! > /tmp/90tc-dev.pid
```

**Stoppen:** `kill $(cat /tmp/90tc-dev.pid)`  
**Logs:** `tail -f /tmp/90tc-dev.log`

Lokale Artefakte sind in `.gitignore` — kein Konflikt mit dem Pi möglich:

| Pfad | Zweck | Im Repo? |
|---|---|---|
| `server/venv/` | Python-Umgebung | nein |
| `server/db/` | lokale SQLite | nein |
| `server/static/` | Symlink → Repo-Root | nein |
| `server/.env` | lokale Konfiguration (SECURE_COOKIE=false) | nein |

**Hinweis:** Ohne HTTPS kein Service Worker / kein Push im lokalen Netz — für UI-Tests reicht HTTP.

---

## Workflow für Code-Änderungen

```
1. Änderungen in index.html / sw.js / server/ machen
2. Lokal testen: http://192.168.178.110:8080
3. JS validieren:
   node -e "const h=require('fs').readFileSync('index.html','utf8');
     new Function(h.slice(h.indexOf('<script>')+8,h.lastIndexOf('</script>')));
     console.log('OK')"
4. APP_VERSION in index.html erhöhen
5. PROJEKTSTATUS.md aktualisieren (Version + Commit)
6. Committen & pushen:
   git add index.html sw.js manifest.json PROJEKTSTATUS.md
   git commit -m "..."
   git push origin main
7. Auf Pi deployen:
   ssh pi@dartsserver
   bash /home/pi/90tc-repo/server/deploy.sh
```

PAT: im Memory-System der KI gespeichert (memory/project_90tc.md).

---

## Alle behobenen Bugs

| Version | # | Bug | Fix |
|---|---|---|---|
| <1.1 | 1 | Splash-Screen immer sichtbar | `.active`-Selektor korrigiert |
| <1.1 | 2 | Umfänge-Felder abgeschnitten | Flex statt Grid |
| <1.1 | 3 | Kalender zeigt Vortag | `toISOString()` → lokale Datumsfunktion |
| <1.1 | 4 | URL-Import trägt keine Werte ein | Dezimalkomma-Konvertierung `_cv()` |
| 1.1.0 | 5 | Fotos aus Fotorolle nicht wählbar | `capture="camera"` entfernt |
| 1.1.0 | 6 | Tageseintrag an Check-Tagen blockiert | `openDay()` → immer `openEntry()` + Check-Banner |
| 1.1.0 | 7 | Kalender-Dots unsichtbar | CSS: `.cal-day-dot.done/.partial` |
| 1.1.0 | 8 | PWA startet ohne Daten | iOS-Design → Export/Import-Workaround |
| 1.2.1 | 9 | App startet nicht (weiße Seite) | Doppeltes `const cfg` in `renderSettings()` |
| 1.2.2 | 10 | Notifications trotz Berechtigung stumm | `new Notification()` → `SW.showNotification()` |
| 1.5.1 | 11 | Auth-Screen erscheint nicht (JS-Syntaxfehler) | `async/await` statt `.then()` in `init()` |
| 1.5.2 | 12 | Auth-Screen bleibt unsichtbar | CSS `.active`-Selektor + inline-style entfernt |
| 1.5.3 | 13 | Import lädt nicht zum Server hoch | `_doImport` setzt dirty-queue + ruft `sync()` auf |
| 1.7.0 | 14 | Alte App-Version nach Update im Browser | sw.js auf Network-First für index.html umgestellt |
| 1.7.0 | 15 | Changelog-Modal erscheint nicht nach Cache-Clear | `lastSeen=null` + `settings` vorhanden → `lastSeen='0.0.0'` |
| 1.7.0 | 16 | PWA vom Homescreen lädt alte Version | `controllerchange`-Listener löst automatischen Reload aus |
| 1.7.0 | 17 | Tägliche Erinnerung kommt nie | `checkReminderNotif()` nur bei URL-Import aufgerufen → jetzt bei jedem Start |
| 1.8.0 | 18 | Push-Erinnerung nur wenn App geöffnet | Umstieg auf echtes Web Push (VAPID): Server sendet Push vom Pi, SW zeigt Notification unabhängig vom App-Status |

---

## Bekannte Einschränkungen

| Einschränkung | Workaround |
|---|---|
| localStorage ~5 MB Limit | Fotos sparsam einsetzen |
| iOS löscht PWA-Storage bei Inaktivität | Daten liegen jetzt auf dem Server — kein Datenverlust mehr |
| ~~Service Worker Cache nach Updates~~ | ~~SW-Cache leeren~~ → behoben in 1.7.0 (Network-First + controllerchange) |
| Fotos noch in localStorage (Base64) | Zukünftiger Upload auf Server (Phase 6 aus Migrationsplan) |
