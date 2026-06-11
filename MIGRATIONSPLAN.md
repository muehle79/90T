# Migrationsplan: 90TC von GitHub Pages auf eigenen Server mit Multi-User

Stand: 2026-06-11 · Basis: App-Version 1.4.4

## Ausgangslage

- Single-File-PWA (`index.html`), Deployment via GitHub Pages (https://muehle79.github.io/90T/)
- Alle Daten im localStorage, Key-Value mit Prefix `90tc_`:
  `settings`, `statusQuo`, `daily_YYYY-MM-DD`, `weekly_N`, `monthly_N`, `final`, `lastExport`, `notifShown_*`
- Vorhanden: Domain bei Strato (zeigt auf Dart-Homepage), Cloudflare Tunnel, eigener Server

## Zielarchitektur

```
Browser/PWA ── HTTPS ──> Cloudflare ── Tunnel (cloudflared) ──> eigener Server
                                                                  ├── Webserver (statische Dateien: index.html, sw.js, …)
                                                                  ├── API-Backend (Auth + Daten-Sync)
                                                                  └── Datenbank (SQLite)
```

**Stack-Empfehlung:** Node.js (Fastify oder Express) + **SQLite**.
Begründung: Die App ist bewusst minimalistisch (Single-File, kein Framework). Postgres/MySQL wäre Overkill —
SQLite ist eine Datei, braucht keinen DB-Prozess, Backups sind simples Datei-Kopieren.
Für ein paar Dutzend Nutzer völlig ausreichend.

---

## Phase 1: DNS & Cloudflare Tunnel

Cloudflare Tunnel mit eigenem Hostname funktioniert nur, wenn die **Domain als Zone im
Cloudflare-Account** liegt (Nameserver bei Cloudflare).

1. **Falls Nameserver noch bei Strato:** Domain in Cloudflare als Zone hinzufügen, bei Strato die
   Cloudflare-Nameserver eintragen.
   **Achtung:** Vorher alle bestehenden DNS-Records (A-Record der Dart-Homepage, MX für E-Mail!) in
   Cloudflare nachbilden, sonst ist die Homepage offline. Die Dart-Homepage bleibt bei Strato
   gehostet — nur die DNS-Verwaltung wandert.
2. **Subdomain für die App anlegen:** z. B. `90tc.deine-domain.de`. Im Cloudflare Zero Trust
   Dashboard (oder per `config.yml`) einen **Public Hostname** im bestehenden Tunnel anlegen:
   - `90tc.deine-domain.de` → `http://localhost:8080` (Backend auf dem Server)
3. HTTPS terminiert Cloudflare automatisch — kein eigenes Zertifikat auf dem Server nötig.

## Phase 2: Server-Setup

1. **Kein nginx nötig:** Das Node-Backend liefert die statischen Dateien selbst aus
   (`GET /` → `index.html`, dazu `/api/*`). Weniger bewegliche Teile.
2. **Betrieb als Dienst:** systemd-Unit oder Docker-Container (`restart: always`).
   Bei Docker: Compose-File mit App-Container + Volume für die SQLite-Datei.
3. **Backup:** Cron-Job, täglich:
   ```sh
   sqlite3 app.db ".backup /backup/app-$(date +%F).db"
   ```
   (Online-Backup, kein Lock-Problem.)

## Phase 3: Backend (neu zu bauen)

Das Datenmodell der App ist ein Key-Value-Store — das Backend bildet das 1:1 ab:

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL,          -- bcrypt/argon2
  created_at TEXT NOT NULL
);

CREATE TABLE kv (
  user_id INTEGER NOT NULL REFERENCES users(id),
  key TEXT NOT NULL,              -- 'settings', 'daily_2026-06-11', 'weekly_3', ...
  value TEXT NOT NULL,            -- JSON, wie bisher im localStorage
  updated_at INTEGER NOT NULL,    -- Unix-Millisekunden, für Sync-Konflikte
  PRIMARY KEY (user_id, key)
);
```

**API-Endpunkte (minimal):**

| Endpunkt | Zweck |
|---|---|
| `POST /api/register` | E-Mail + Passwort, bcrypt-Hash speichern |
| `POST /api/login` | Session-Cookie setzen (httpOnly, Secure) |
| `POST /api/logout` | Session beenden |
| `GET /api/sync?since=<ts>` | Alle Keys des Nutzers, die sich seit `<ts>` geändert haben |
| `PUT /api/kv` | Batch-Upsert: `[{key, value, updated_at}, ...]` |

Dazu: Rate-Limiting auf Login/Register und optional ein **Invite-Code** für die Registrierung,
wenn nur Familie/Freunde die App nutzen sollen (verhindert Spam-Accounts).

## Phase 4: App-Anpassungen (`index.html`)

Größter Teil der Arbeit. Vorteil: Alle Lese-/Schreibzugriffe laufen durch den `S`-Wrapper —
die Sync-Logik ist an einer einzigen Stelle einbaubar.

1. **Offline-first beibehalten:** localStorage bleibt primärer Speicher (App funktioniert weiter
   ohne Netz). Neu: `S.set()` markiert den Key zusätzlich in einer Dirty-Queue (`90tc_dirty`)
   mit Zeitstempel.
2. **Sync-Schicht:** Funktion `sync()`, die
   (a) die Dirty-Queue per `PUT /api/kv` hochlädt und
   (b) per `GET /api/sync?since=` Server-Änderungen in den localStorage übernimmt.
   Konfliktauflösung: **Last-Write-Wins pro Key** anhand `updated_at` — bei einer Tagebuch-App
   mit einem Eintrag pro Tag praktisch immer korrekt.
   Aufruf bei App-Start, nach jedem Speichern (debounced) und bei `online`-Event.
3. **Login-Screen:** Vor dem Setup-Wizard ein Auth-Screen (Login/Registrieren). Nach Login:
   Server hat Daten → herunterladen; localStorage hat Daten und Account ist leer → hochladen
   (deckt zugleich die Migration ab).
4. **Multi-User auf demselben Gerät** (falls gewünscht): localStorage-Prefix von `90tc_` auf
   `90tc_<userId>_` erweitern, sonst vermischen sich Daten beim Account-Wechsel.
   Einfacher Kompromiss: beim Logout lokale Daten löschen (nach erfolgreichem Sync).
5. **Service Worker (`sw.js`):** `/api/*` vom Caching ausnehmen (network-only), statische Dateien
   weiter cachen. `APP_VERSION`-Mechanismus bleibt.
6. **Fotos:** Liegen aktuell als Base64 im localStorage (5-MB-Limit). Empfehlung: Endpunkt
   `POST /api/photos` + Ablage als Datei auf dem Server — löst das 5-MB-Problem und das
   iOS-Storage-Lösch-Problem gleich mit. Kann auch als Phase 6 nachgezogen werden.

## Phase 5: Migration & Umstellung

1. Backend + angepasste App auf dem Server deployen, unter `90tc.deine-domain.de` testen
   (parallel zu GitHub Pages, das bleibt erstmal unangetastet).
2. Auf dem Handy: In der alten PWA **Export** ausführen, in der neuen App Account anlegen und
   importieren — bzw. der Auto-Upload aus Phase 4 Punkt 3 erledigt das.
3. Neue PWA vom neuen Host installieren (PWA-Installationen sind an den Origin gebunden —
   die alte GitHub-Pages-Installation muss ersetzt werden).
4. Nach erfolgreicher Verifikation: GitHub-Pages-Version durch eine Weiterleitungsseite auf die
   neue URL ersetzen.

## Sicherheits-Checkliste

- Passwörter nur als bcrypt/argon2-Hash, Session-Cookies `httpOnly` + `Secure` + `SameSite=Lax`
- Rate-Limiting auf Auth-Endpunkte, Invite-Code für Registrierung
- Optional: Cloudflare Access als zusätzliche Schutzschicht vor dem Hostname
- Tägliche SQLite-Backups, zusätzlich an einen zweiten Ort kopiert

## Aufwandsschätzung & Reihenfolge

| Schritt | Aufwand |
|---|---|
| DNS/Tunnel-Hostname einrichten | ~1 h (wenn Zone schon bei Cloudflare) |
| Backend (Auth + KV-Sync, SQLite) | 1–2 Tage |
| App-Anpassung (Auth-Screen, Sync im `S`-Wrapper, SW) | 2–3 Tage |
| Migration + Tests (v. a. iOS-PWA) | 0,5–1 Tag |
| Foto-Upload auf Server (optional, empfohlen) | 0,5–1 Tag |

Sinnvollste Reihenfolge = Phasen-Reihenfolge: Nach Phase 3 lässt sich das Backend isoliert mit
`curl` testen, bevor die App angefasst wird.

## Offene Entscheidungen

1. Liegt die Domain-Zone schon im Cloudflare-Account oder nur der Tunnel?
2. Registrierung offen oder per Invite-Code?
3. Welche Subdomain soll die App bekommen?
