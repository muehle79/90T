# 90TC — Schritt-für-Schritt-Migrationsplan (auf vorhandenen Server)

**Stand:** 2026-06-11  
**Basis:** App v1.4.4 · IST-Dokumentation Blue Bulls Server · MIGRATIONSPLAN.md  
**Ziel-URL:** `https://90tc.blue-bulls-flechtorf.de`

---

## Ausgangslage auf einen Blick

| Was | Ist |
|---|---|
| Domain-Zone | bereits bei **Cloudflare** (NS: valentin / ximena.ns.cloudflare.com) |
| Strato | nur Registrar — DNS-Änderungen immer in **Cloudflare**, nie in Strato |
| Bestehender Tunnel | `darts-tunnel` · ID `3a2878de-1b4a-45b3-9383-865a4a6dee03` |
| Tunnel-Ziel heute | `www.blue-bulls-flechtorf.de` → `localhost:8000` (Gunicorn Darts-App) |
| Flask/Gunicorn | läuft auf Port **8000** als `root` (flaskapp.service) |
| Nginx | läuft auf Port 80, wird vom Tunnel aktuell **nicht** genutzt |
| Server | Raspberry Pi 4, Debian 12, `/home/pi/dart-pyramide` |
| Stack-Entscheidung | **Python / Flask** (konsistent mit vorhandenem Stack, kein Node.js) |
| Neue App läuft auf | Port **8080** (kein Konflikt mit 8000) |

---

## Zielarchitektur

```
Browser / iOS-PWA
      │ HTTPS
      ▼
Cloudflare (Zone: blue-bulls-flechtorf.de)
      │ SSL-Terminierung (Modus: Full, Zertifikat bereits aktiv)
      ▼
Cloudflare Tunnel „darts-tunnel"
(ID: 3a2878de-1b4a-45b3-9383-865a4a6dee03)
      │
      ├─► www.blue-bulls-flechtorf.de → localhost:8000  (Darts-App, unverändert)
      └─► 90tc.blue-bulls-flechtorf.de → localhost:8080 (90TC-App, NEU)
      │
      ▼
cloudflared.service auf dem Raspi
      │
      ├─► Gunicorn Port 8000 → flaskapp.service (Darts, unverändert)
      └─► Gunicorn Port 8080 → 90tc.service (NEU)
            │
            ▼
         Flask-App /home/pi/90tc-app
            ├── statische Dateien (index.html, sw.js, …)
            └── API /api/* (Auth + KV-Sync)
            │
            ▼
         SQLite /home/pi/90tc-app/db/90tc.db
```

Nginx bleibt wie bisher installiert aber inaktiv für den Tunnel-Traffic.

---

## Phase 0 — Vorbereitung (lokal, kein Downtime-Risiko)

### 0.1 — Bestehende Dienste sichern

Vor jeder Änderung am Server:

```bash
# SSH-Verbindung zum Raspi
ssh pi@192.168.178.144

# Aktuellen Stand der laufenden Dienste prüfen
sudo systemctl status flaskapp.service --no-pager
sudo systemctl status cloudflared --no-pager
sudo systemctl status nginx --no-pager

# Datenbank-Backup manuell anlegen
cp /home/pi/dart-pyramide/db/pyramide.db \
   /home/pi/dart-pyramide/db/pyramide_backup_$(date +%Y%m%d_%H%M%S).db
```

### 0.2 — Ausstehende Systempflege erledigen (aus IST-Dokumentation)

Diese Punkte sollten vor der Migration erledigt werden:

```bash
# systemd-Warnung beheben (flaskapp.service wurde auf Disk geändert)
sudo systemctl daemon-reload
sudo systemctl status flaskapp.service --no-pager
# → prüfen ob noch active (running), dann ist nichts passiert

# cloudflared aktualisieren (aktuell 2025.6.1, empfohlen 2026.6.0)
sudo systemctl stop cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm \
     -o /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared
cloudflared --version   # muss 2026.6.0 zeigen
sudo systemctl start cloudflared
sudo systemctl status cloudflared --no-pager
# Log-Prüfung: "Registered tunnel connection" muss erscheinen
journalctl -u cloudflared -n 30 --no-pager
```

---

## Phase 1 — Cloudflare DNS: neue Subdomain anlegen

**Wo:** Cloudflare Dashboard → Zone `blue-bulls-flechtorf.de` → DNS

### 1.1 — CNAME-Eintrag für 90tc hinzufügen

| Feld | Wert |
|---|---|
| Typ | CNAME |
| Name | `90tc` |
| Ziel | `3a2878de-1b4a-45b3-9383-865a4a6dee03.cfargotunnel.com` |
| Proxy | **Aktiv** (oranges Wolken-Symbol) |
| TTL | Auto |

Das ist dieselbe Tunnel-ID wie für `www`. Der Tunnel kann beliebig viele Hostnamen bedienen.

**Prüfung nach dem Setzen (vom eigenen Rechner, dauert ca. 1 Min.):**

```bash
dig CNAME 90tc.blue-bulls-flechtorf.de +short
# → kein direkter CNAME sichtbar (proxied), aber Record muss gesetzt sein
# Alternative Prüfung:
curl -I https://90tc.blue-bulls-flechtorf.de
# → gibt 502/404 zurück (Backend noch nicht da) — das ist OK, DNS + Tunnel funktionieren
```

### 1.2 — SSL/TLS: nichts zu tun

Das Cloudflare Universal Certificate gilt bereits für `*.blue-bulls-flechtorf.de` (läuft bis 2026-09-09). Die neue Subdomain ist damit automatisch abgedeckt. Modus bleibt **Full**.

### 1.3 — Strato: keine Aktion nötig

Nameserver stehen bereits auf Cloudflare. In Strato wird nichts verändert. Die STRATO-Mail-DNS-Einträge (MX, SPF, DKIM) bleiben in Cloudflare erhalten und werden nicht berührt.

---

## Phase 2 — Cloudflare Tunnel: neuen Hostname registrieren

Der Tunnel `darts-tunnel` bekommt einen zweiten öffentlichen Hostname.

**Es gibt zwei Wege — Empfehlung: config.yml (Variante A), weil sie versionierbar ist.**

### 2.1 — Variante A: config.yml erweitern (empfohlen)

```bash
ssh pi@192.168.178.144
sudo nano /home/pi/.cloudflared/config.yml
```

**Neue config.yml:**

```yaml
tunnel: darts-tunnel
credentials-file: /home/pi/.cloudflared/3a2878de-1b4a-45b3-9383-865a4a6dee03.json

ingress:
  - hostname: www.blue-bulls-flechtorf.de
    service: http://localhost:8000

  - hostname: 90tc.blue-bulls-flechtorf.de
    service: http://localhost:8080

  - service: http_status:404
```

**Wichtig:** Die Reihenfolge ist entscheidend. Der Fallback `http_status:404` muss immer als letzter Eintrag stehen.

```bash
# Syntaxprüfung
cloudflared tunnel ingress validate

# cloudflared neu starten
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager

# Erfolgsindikator prüfen
journalctl -u cloudflared -n 30 --no-pager
# → "Registered tunnel connection" für beide FRA-Verbindungen
```

### 2.2 — Variante B: Zero Trust Dashboard (alternativ)

Falls du die GUI bevorzugst:  
Cloudflare Dashboard → Zero Trust → Networks → Tunnels → `darts-tunnel` → Edit → Public Hostnames → Add a public hostname:

- Subdomain: `90tc`
- Domain: `blue-bulls-flechtorf.de`
- Service Type: HTTP
- URL: `localhost:8080`

Bei Variante B muss die `config.yml` **nicht** angepasst werden — die Konfiguration liegt dann in der Cloudflare-Cloud.  
**Achtung:** Variante A und B gleichzeitig für denselben Hostname führen zu Konflikten. Nur einen Weg wählen.

### 2.3 — Connector-ID / Tunnel-Verbindungen

Die Connector-ID `1d3b0771-6004-4739-9d7a-bc72bb16c686` identifiziert den laufenden `cloudflared`-Prozess auf dem Raspi. Diese ändert sich **nicht** durch das Hinzufügen eines neuen Hostnames. Kein Handlungsbedarf.

Die 4 Edge-Verbindungen (fra03/08/13/14) bleiben bestehen.

---

## Phase 3 — Server-Setup: 90TC-Projektverzeichnis anlegen

```bash
ssh pi@192.168.178.144

# Verzeichnisstruktur anlegen
mkdir -p /home/pi/90tc-app/{db,static,templates,backups}

# Python venv erstellen (Python 3.11 ist auf dem Raspi vorhanden)
cd /home/pi/90tc-app
python3 -m venv venv

# Abhängigkeiten installieren
source venv/bin/activate
pip install flask gunicorn bcrypt
pip freeze > requirements.txt
deactivate
```

**Finale Verzeichnisstruktur:**

```
/home/pi/90tc-app/
├── app.py                  # Flask-App (Auth + API + Static-Serving)
├── requirements.txt
├── .env                    # SECRET_KEY (nie in Git!)
├── db/
│   └── 90tc.db             # wird beim ersten Start erstellt
├── static/
│   ├── index.html          # aus GitHub-Repo kopieren
│   ├── sw.js
│   ├── manifest.json
│   ├── import.html
│   ├── icon-192.png
│   └── icon-512.png
├── templates/              # (leer, Flask serviert index.html als static file)
├── backups/                # Backup-Ziel für Cron-Job
└── venv/
```

---

## Phase 4 — Backend: Flask-App bauen

### 4.1 — Datenbankschema (`setup_db.py`)

```bash
nano /home/pi/90tc-app/setup_db.py
```

```python
import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), 'db', '90tc.db')

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT UNIQUE NOT NULL,
            pw_hash    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kv (
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, key)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    con.commit()
    con.close()
    print("DB initialisiert:", DB)

if __name__ == '__main__':
    init_db()
```

```bash
cd /home/pi/90tc-app
source venv/bin/activate
python setup_db.py
# → "DB initialisiert: /home/pi/90tc-app/db/90tc.db"
```

### 4.2 — Environment-Datei

```bash
nano /home/pi/90tc-app/.env
```

```
SECRET_KEY=HIER_EINEN_LANGEN_ZUFALLSSTRING_EINTRAGEN
INVITE_CODE=HIER_EINEN_EINLADUNGSCODE_FUER_REGISTRIERUNG
```

Zufälliger Key generieren:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Rechte absichern:

```bash
chmod 600 /home/pi/90tc-app/.env
```

### 4.3 — Flask-App (`app.py`)

```bash
nano /home/pi/90tc-app/app.py
```

```python
import os, json, sqlite3, bcrypt, secrets
from datetime import datetime
from functools import wraps
from flask import (Flask, request, jsonify, send_from_directory,
                   make_response, g)

# ── Konfiguration ──────────────────────────────────────────────────────────────
BASE   = os.path.dirname(__file__)
DB     = os.path.join(BASE, 'db', '90tc.db')
STATIC = os.path.join(BASE, 'static')

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ['SECRET_KEY']
INVITE_CODE    = os.environ.get('INVITE_CODE', '')   # leer = offen

# ── Datenbank-Hilfsfunktionen ──────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(_): 
    db = g.pop('db', None)
    if db: db.close()

# ── Auth-Hilfsfunktionen ───────────────────────────────────────────────────────
def get_user_from_cookie():
    token = request.cookies.get('90tc_session')
    if not token:
        return None
    db = get_db()
    row = db.execute(
        "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,)
    ).fetchone()
    return row

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_cookie()
        if not user:
            return jsonify({'error': 'nicht angemeldet'}), 401
        g.user = user
        return f(*args, **kwargs)
    return wrapper

# ── Statische Dateien (PWA) ────────────────────────────────────────────────────
@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory(STATIC, 'index.html')

@app.route('/sw.js')
def sw():
    resp = send_from_directory(STATIC, 'sw.js')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC, filename)

# ── Auth-Endpunkte ─────────────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data  = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password', '')
    code  = data.get('invite_code', '')

    if INVITE_CODE and code != INVITE_CODE:
        return jsonify({'error': 'Ungültiger Einladungscode'}), 403
    if not email or '@' not in email:
        return jsonify({'error': 'Ungültige E-Mail'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Passwort zu kurz (min. 8 Zeichen)'}), 400

    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (email, pw_hash) VALUES (?, ?)",
            (email, pw_hash)
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'E-Mail bereits registriert'}), 409

    return jsonify({'ok': True}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data  = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password', '')

    db  = get_db()
    row = db.execute("SELECT id, pw_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not bcrypt.checkpw(pw.encode(), row['pw_hash'].encode()):
        return jsonify({'error': 'Ungültige Anmeldedaten'}), 401

    token = secrets.token_hex(32)
    db.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row['id']))
    db.commit()

    resp = make_response(jsonify({'ok': True, 'userId': row['id']}))
    resp.set_cookie('90tc_session', token,
                    httponly=True, secure=True, samesite='Lax',
                    max_age=60 * 60 * 24 * 365)   # 1 Jahr
    return resp

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    token = request.cookies.get('90tc_session')
    get_db().execute("DELETE FROM sessions WHERE token = ?", (token,))
    get_db().commit()
    resp = make_response(jsonify({'ok': True}))
    resp.delete_cookie('90tc_session')
    return resp

@app.route('/api/me')
@login_required
def me():
    return jsonify({'userId': g.user['id'], 'email': g.user['email']})

# ── KV-Sync-Endpunkte ──────────────────────────────────────────────────────────
@app.route('/api/sync')
@login_required
def sync_get():
    since = int(request.args.get('since', 0))
    db    = get_db()
    rows  = db.execute(
        "SELECT key, value, updated_at FROM kv WHERE user_id = ? AND updated_at > ?",
        (g.user['id'], since)
    ).fetchall()
    return jsonify([{'key': r['key'], 'value': json.loads(r['value']),
                     'updated_at': r['updated_at']} for r in rows])

@app.route('/api/kv', methods=['PUT'])
@login_required
def kv_put():
    items = request.get_json(force=True)
    if not isinstance(items, list):
        return jsonify({'error': 'Liste erwartet'}), 400
    db = get_db()
    for item in items:
        db.execute("""
            INSERT INTO kv (user_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (user_id, key) DO UPDATE
              SET value = excluded.value, updated_at = excluded.updated_at
              WHERE excluded.updated_at > kv.updated_at
        """, (g.user['id'], item['key'],
              json.dumps(item['value']), item['updated_at']))
    db.commit()
    return jsonify({'ok': True, 'written': len(items)})

# ── App-Start ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
```

### 4.4 — Lokaler Test (auf dem Raspi)

```bash
cd /home/pi/90tc-app
source venv/bin/activate

# Erst DB initialisieren (falls noch nicht geschehen)
python setup_db.py

# Test-Start
python app.py &
sleep 2

# Health-Check
curl http://localhost:8080/api/me
# → {"error": "nicht angemeldet"} — das ist korrekt (401)

curl http://localhost:8080/ -I
# → HTTP/1.1 200 OK (index.html wird ausgeliefert)

# Prozess stoppen
kill %1
```

---

## Phase 5 — systemd-Service für die 90TC-App

### 5.1 — Service-Datei anlegen

```bash
sudo nano /etc/systemd/system/90tc.service
```

```ini
[Unit]
Description=90-Tage-Challenge Web App
After=network.target

[Service]
User=pi
Group=pi
WorkingDirectory=/home/pi/90tc-app
EnvironmentFile=/home/pi/90tc-app/.env
Environment="PATH=/home/pi/90tc-app/venv/bin"
ExecStart=/home/pi/90tc-app/venv/bin/gunicorn \
    -w 2 \
    -b 127.0.0.1:8080 \
    --timeout 30 \
    app:app
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Hinweise:**
- `User=pi` (nicht root — besser als beim bestehenden flaskapp.service)
- `-b 127.0.0.1:8080` (nur lokal erreichbar — Cloudflare Tunnel ist der einzige Eingang)
- `-w 2` (2 Worker reichen für die Last; Raspi hat 4 Kerne, aber 90TC ist privat/klein)

```bash
# Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable 90tc.service
sudo systemctl start 90tc.service
sudo systemctl status 90tc.service --no-pager

# Logs prüfen
journalctl -u 90tc.service -n 20 --no-pager
# → "Booting worker with pid: ..." — alles OK
```

### 5.2 — Gunicorn-Erreichbarkeit prüfen

```bash
curl http://127.0.0.1:8080/
# → HTML der index.html (sofern static/index.html bereits vorhanden)

curl http://127.0.0.1:8080/api/me
# → {"error": "nicht angemeldet"}
```

---

## Phase 6 — Nginx: Anpassung (optional, empfohlen)

Der Cloudflare Tunnel zeigt derzeit direkt auf Gunicorn (`:8000` bzw. neu `:8080`). Nginx wird vom Tunnel nicht genutzt, ist aber trotzdem aktiv.

**Empfohlene Aktion:** Nginx als Second-Level-Proxy aufräumen, damit klare Trennung besteht.

```bash
sudo nano /etc/nginx/sites-available/dart-pyramide
```

**Erweiterte nginx-Konfiguration (beide Apps):**

```nginx
# Darts-App (unverändert)
server {
    listen 80;
    server_name www.blue-bulls-flechtorf.de blue-bulls-flechtorf.de;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# 90TC-App (neu)
server {
    listen 80;
    server_name 90tc.blue-bulls-flechtorf.de;

    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Wenn Nginx als Proxy-Layer genutzt werden soll**, muss außerdem die `config.yml` angepasst werden:

```yaml
# config.yml (wenn Tunnel → Nginx → Gunicorn)
ingress:
  - hostname: www.blue-bulls-flechtorf.de
    service: http://localhost:80

  - hostname: 90tc.blue-bulls-flechtorf.de
    service: http://localhost:80

  - service: http_status:404
```

**Entscheidung:** Für den Start empfehle ich, den Tunnel **direkt** auf Gunicorn zu lassen (Variante aus Phase 2). Nginx kann später dazwischen geschaltet werden.

```bash
# Nginx-Konfiguration testen (nach Änderungen)
sudo nginx -t
sudo systemctl reload nginx
```

---

## Phase 7 — App-Dateien auf den Server kopieren

Die statischen PWA-Dateien müssen in `/home/pi/90tc-app/static/` landen.

**Option A: direkt vom GitHub-Repo klonen (empfohlen):**

```bash
ssh pi@192.168.178.144
cd /tmp
git clone https://muehle79:PAT_HIER@github.com/muehle79/90T.git 90t-tmp

cp 90t-tmp/index.html   /home/pi/90tc-app/static/
cp 90t-tmp/sw.js        /home/pi/90tc-app/static/
cp 90t-tmp/manifest.json /home/pi/90tc-app/static/
cp 90t-tmp/import.html  /home/pi/90tc-app/static/
cp 90t-tmp/icon-192.png /home/pi/90tc-app/static/
cp 90t-tmp/icon-512.png /home/pi/90tc-app/static/

rm -rf /tmp/90t-tmp
```

**Option B: scp vom eigenen Mac:**

```bash
scp /Users/lars/Documents/Claude/Projects/90Tage\ Challenge\ APP/index.html \
    pi@192.168.178.144:/home/pi/90tc-app/static/
# (analog für sw.js, manifest.json, import.html, icon-*.png)
```

Danach Service-Neustart:

```bash
sudo systemctl restart 90tc.service

# Endtest auf dem Raspi
curl http://127.0.0.1:8080/ | head -5
# → Anfang des index.html HTML
```

---

## Phase 8 — App-Anpassung: Sync-Schicht in index.html

Das ist die aufwendigste Phase. Die PWA muss um Auth und Server-Sync erweitert werden. Alle Änderungen im `index.html`.

### 8.1 — S-Wrapper erweitern (Dirty-Queue)

Die bestehende Struktur `S = { get, set, del, clear }` wird ergänzt:

```javascript
// Dirty-Queue: welche Keys wurden seit letztem Sync verändert?
const DIRTY_KEY = '90tc_dirty';

const S = {
  get(k)    { /* unverändert */ },
  
  set(k, v) {
    // 1. wie bisher in localStorage schreiben
    localStorage.setItem('90tc_' + k, JSON.stringify(v));
    // 2. Key in Dirty-Queue eintragen
    const dirty = S._getDirty();
    dirty[k] = Date.now();
    localStorage.setItem(DIRTY_KEY, JSON.stringify(dirty));
  },
  
  del(k)    { /* unverändert, Dirty-Queue nicht nötig bei Delete */ },
  clear()   { /* unverändert */ },
  
  _getDirty() {
    try { return JSON.parse(localStorage.getItem(DIRTY_KEY) || '{}'); } 
    catch { return {}; }
  },
  _clearDirty() { localStorage.removeItem(DIRTY_KEY); }
};
```

### 8.2 — Sync-Funktion

```javascript
const API_BASE = '';  // same-origin — kein Cross-Origin-Problem

let _syncInProgress = false;

async function sync() {
  if (_syncInProgress || !navigator.onLine) return;
  _syncInProgress = true;
  try {
    // a) Dirty-Keys hochladen
    const dirty = S._getDirty();
    const keys = Object.keys(dirty);
    if (keys.length > 0) {
      const items = keys.map(k => ({
        key: k,
        value: S.get(k),
        updated_at: dirty[k]
      }));
      const r = await fetch('/api/kv', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(items),
        credentials: 'include'
      });
      if (r.ok) S._clearDirty();
    }

    // b) Server-Änderungen herunterladen
    const lastSync = parseInt(localStorage.getItem('90tc_lastSync') || '0');
    const r2 = await fetch('/api/sync?since=' + lastSync, { credentials: 'include' });
    if (r2.ok) {
      const serverItems = await r2.json();
      for (const item of serverItems) {
        // Nur überschreiben wenn Server neuer ist
        const localTs = S._getDirty()[item.key] || 0;
        if (item.updated_at > localTs) {
          localStorage.setItem('90tc_' + item.key, JSON.stringify(item.value));
        }
      }
      localStorage.setItem('90tc_lastSync', Date.now().toString());
    }
  } catch (e) {
    console.warn('Sync fehlgeschlagen:', e);
  } finally {
    _syncInProgress = false;
  }
}

// Sync auslösen: beim Start + nach jedem Speichern (debounced) + bei Online-Event
window.addEventListener('online', sync);
// In App.init() am Ende: sync();
// In jedem Speichern-Handler: setTimeout(sync, 1000);
```

### 8.3 — Login-Screen (`screen-auth`) hinzufügen

Vor `screen-splash` einen neuen Screen einfügen:

```html
<div id="screen-auth" class="screen">
  <div class="auth-box">
    <h2>90-Tage-Challenge</h2>
    <div id="auth-tabs">
      <button onclick="App.authTab('login')" id="tab-login" class="active">Anmelden</button>
      <button onclick="App.authTab('register')" id="tab-register">Registrieren</button>
    </div>

    <div id="form-login">
      <input type="email" id="auth-email" placeholder="E-Mail">
      <input type="password" id="auth-pw" placeholder="Passwort">
      <button onclick="App.login()">Anmelden</button>
    </div>

    <div id="form-register" style="display:none">
      <input type="email" id="reg-email" placeholder="E-Mail">
      <input type="password" id="reg-pw" placeholder="Passwort (min. 8 Zeichen)">
      <input type="text" id="reg-code" placeholder="Einladungscode">
      <button onclick="App.register()">Registrieren</button>
    </div>

    <div id="auth-msg" style="color:red;margin-top:8px"></div>
  </div>
</div>
```

```javascript
// In App-Objekt ergänzen:
authTab(tab) {
  document.getElementById('form-login').style.display = tab === 'login' ? '' : 'none';
  document.getElementById('form-register').style.display = tab === 'register' ? '' : 'none';
},

async login() {
  const email = document.getElementById('auth-email').value;
  const pw    = document.getElementById('auth-pw').value;
  const r = await fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email, password: pw}),
    credentials: 'include'
  });
  if (r.ok) {
    await sync();         // Server-Daten herunterladen
    App.init();           // App normal starten
  } else {
    const e = await r.json();
    document.getElementById('auth-msg').textContent = e.error;
  }
},

async register() {
  const email = document.getElementById('reg-email').value;
  const pw    = document.getElementById('reg-pw').value;
  const code  = document.getElementById('reg-code').value;
  const r = await fetch('/api/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email, password: pw, invite_code: code}),
    credentials: 'include'
  });
  if (r.ok) {
    App.authTab('login');
    document.getElementById('auth-msg').style.color = 'green';
    document.getElementById('auth-msg').textContent = 'Registriert! Jetzt anmelden.';
  } else {
    const e = await r.json();
    document.getElementById('auth-msg').textContent = e.error;
  }
},
```

### 8.4 — App-Start-Logik anpassen

```javascript
// App.init() ganz oben ergänzen:
async init() {
  // 1. Anmeldestatus prüfen
  const r = await fetch('/api/me', { credentials: 'include' });
  if (!r.ok) {
    App.showScreen('screen-auth');
    return;
  }
  // 2. Sync starten (im Hintergrund)
  sync();
  // 3. Restliche Init-Logik wie bisher...
}
```

### 8.5 — Service Worker anpassen (`sw.js`)

```javascript
// API-Calls nicht cachen — immer ans Netz
self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) {
    e.respondWith(fetch(e.request));  // network-only
    return;
  }
  // Statische Dateien: Cache-First wie bisher
  // ...
});
```

### 8.6 — manifest.json: Start-URL anpassen

```json
{
  "start_url": "https://90tc.blue-bulls-flechtorf.de/",
  "scope": "https://90tc.blue-bulls-flechtorf.de/"
}
```

---

## Phase 9 — Backup-Cron für 90TC-Datenbank

```bash
crontab -e   # als Benutzer pi
```

Zeile hinzufügen:

```cron
# 90TC-Datenbank täglich um 03:30 Uhr sichern (Online-Backup, kein Lock)
30 3 * * * sqlite3 /home/pi/90tc-app/db/90tc.db ".backup /home/pi/90tc-app/backups/90tc-$(date +\%F).db"

# Backups älter als 30 Tage löschen
35 3 * * * find /home/pi/90tc-app/backups/ -name "*.db" -mtime +30 -delete
```

---

## Phase 10 — Testplan vor Livegang

### 10.1 — Backend-Tests (auf dem Raspi, mit curl)

```bash
BASE="http://127.0.0.1:8080"

# Statische Dateien
curl -I $BASE/
# → 200 OK, Content-Type: text/html

curl -I $BASE/sw.js
# → 200 OK, Cache-Control: no-cache

# Registrierung
curl -s -X POST $BASE/api/register \
     -H "Content-Type: application/json" \
     -d '{"email":"lars@test.de","password":"test1234","invite_code":"DEIN_CODE"}'
# → {"ok": true}

# Login + Cookie speichern
curl -s -c /tmp/cookies.txt -X POST $BASE/api/login \
     -H "Content-Type: application/json" \
     -d '{"email":"lars@test.de","password":"test1234"}'
# → {"ok": true, "userId": 1}

# Auth-Check
curl -s -b /tmp/cookies.txt $BASE/api/me
# → {"userId": 1, "email": "lars@test.de"}

# KV schreiben
curl -s -b /tmp/cookies.txt -X PUT $BASE/api/kv \
     -H "Content-Type: application/json" \
     -d '[{"key":"settings","value":{"startDate":"2026-06-11"},"updated_at":1749600000000}]'
# → {"ok": true, "written": 1}

# KV lesen
curl -s -b /tmp/cookies.txt "$BASE/api/sync?since=0"
# → [{"key":"settings","value":{"startDate":"2026-06-11"},"updated_at":...}]

# Logout
curl -s -b /tmp/cookies.txt -X POST $BASE/api/logout
# → {"ok": true}

rm /tmp/cookies.txt
```

### 10.2 — Tunnel-Test

```bash
# Von außen (vom eigenen Mac oder Handy)
curl -I https://90tc.blue-bulls-flechtorf.de/
# → 200 OK, Server: cloudflare

curl https://90tc.blue-bulls-flechtorf.de/api/me
# → {"error": "nicht angemeldet"} — korrekt, bedeutet: Tunnel + Flask + Auth funktioniert
```

### 10.3 — iOS-PWA-Test

1. Safari auf iPhone → `https://90tc.blue-bulls-flechtorf.de`
2. Teilen → „Zum Home-Bildschirm" → PWA installieren
3. PWA öffnen → Login-Screen erscheint
4. Registrieren + Anmelden
5. Challenge einrichten (Startdatum, Name, Ziele)
6. Tageseintrag anlegen
7. iPhone in Flugmodus → App öffnen → Tageseintrag bearbeiten (offline)
8. Flugmodus aus → Sync sollte automatisch starten
9. Auf zweitem Gerät anmelden → Daten sollen erscheinen ✓

---

## Phase 11 — Parallelbetrieb und Migration

### 11.1 — GitHub Pages bleibt zunächst aktiv

Die bestehende PWA auf `muehle79.github.io/90T/` bleibt unangetastet. Beide Versionen laufen parallel.

### 11.2 — Datenmigration (bestehende App-Daten retten)

Auf dem iPhone in der **alten PWA** (GitHub Pages):

1. Einstellungen → Daten → Export → JSON kopieren
2. Notizen-App → Einträge einfügen (Zwischenspeicher)

In der **neuen PWA** (`90tc.blue-bulls-flechtorf.de`):

1. Account anlegen + anmelden
2. Einstellungen → Daten → Import → JSON einfügen → Laden

Die Import-Funktion ist in der App bereits implementiert — sie schreibt in localStorage, Sync lädt die Daten automatisch hoch.

### 11.3 — Alte PWA ablösen

Erst wenn die neue App stabil läuft:

```bash
# Auf dem Mac: Weiterleitungsseite auf GitHub Pages pushen
cd /tmp/90t-repo
cat > index.html << 'EOF'
<!DOCTYPE html><html><head>
<meta http-equiv="refresh" content="0; url=https://90tc.blue-bulls-flechtorf.de/">
<title>Umgezogen</title></head>
<body>Die App ist umgezogen → <a href="https://90tc.blue-bulls-flechtorf.de/">zur neuen Adresse</a></body>
</html>
EOF
git add index.html
git commit -m "redirect: App zu 90tc.blue-bulls-flechtorf.de umgezogen"
git push origin main
```

---

## Offene Entscheidungen (vor Start klären)

| # | Frage | Optionen |
|---|---|---|
| 1 | Einladungscode | Ja (privat, nur Familie) / Nein (offen) |
| 2 | Welche Subdomain | `90tc.blue-bulls-flechtorf.de` oder andere? |
| 3 | Tunnel via Nginx oder direkt | Direkt (einfacher, empfohlen zum Start) |
| 4 | Fotos auf Server (Phase 5 aus MIGRATIONSPLAN) | Jetzt oder später? |

---

## Übersicht: Dateien und Dienste nach der Migration

| Komponente | Pfad / Details |
|---|---|
| Cloudflare Zone | `blue-bulls-flechtorf.de` (unverändert) |
| Neuer DNS-Record | `90tc` CNAME → `3a2878de-...cfargotunnel.com` (proxied) |
| Tunnel | `darts-tunnel` · ID `3a2878de-1b4a-45b3-9383-865a4a6dee03` |
| cloudflared config | `/home/pi/.cloudflared/config.yml` (um 90tc-Eintrag erweitert) |
| cloudflared service | `/etc/systemd/system/cloudflared.service` (unverändert) |
| 90TC systemd service | `/etc/systemd/system/90tc.service` (NEU) |
| 90TC Flask-App | `/home/pi/90tc-app/app.py` |
| 90TC statische Dateien | `/home/pi/90tc-app/static/` |
| 90TC Datenbank | `/home/pi/90tc-app/db/90tc.db` |
| 90TC .env | `/home/pi/90tc-app/.env` (SECRET_KEY, INVITE_CODE) |
| Gunicorn Port | `127.0.0.1:8080` |
| Darts-App | `/home/pi/dart-pyramide` (unverändert, Port 8000) |
| Nginx | bleibt installiert, server_name konkretisieren empfohlen |
| SSL/TLS | Cloudflare Universal Cert (unverändert, gilt für `*.blue-bulls-flechtorf.de`) |
| Backup-Cron | täglich 03:30 Uhr → `/home/pi/90tc-app/backups/` |

---

## Aufwandsschätzung

| Phase | Was | Aufwand |
|---|---|---|
| 0 | Vorbereitung + cloudflared-Update | 30 Min. |
| 1 | Cloudflare DNS: CNAME anlegen | 5 Min. |
| 2 | Tunnel config.yml erweitern | 10 Min. |
| 3 | Verzeichnisstruktur + venv | 10 Min. |
| 4 | Flask-App (app.py, setup_db.py) | 1–2 h |
| 5 | systemd-Service | 10 Min. |
| 6 | Nginx (optional) | 20 Min. |
| 7 | Statische Dateien deployen | 10 Min. |
| 8 | App-Anpassung (Auth-Screen, Sync) | 2–4 h |
| 9 | Backup-Cron | 5 Min. |
| 10 | Testplan durchführen | 1 h |
| 11 | Migration + Parallelbetrieb | 30 Min. |
| **Gesamt** | | **ca. 6–9 h** |

---

*Erstellt: 2026-06-11 · Basis: App v1.4.4 · Server IST-Stand 2026-06-11*
