import os, json, sqlite3, bcrypt, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, make_response, g

try:
    from pywebpush import webpush, WebPushException
    PUSH_AVAILABLE = True
except ImportError:
    PUSH_AVAILABLE = False

BASE   = os.path.dirname(os.path.abspath(__file__))
DB     = os.path.join(BASE, 'db', '90tc.db')
STATIC = os.path.join(BASE, 'static')

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ['SECRET_KEY']
INVITE_CODE         = os.environ.get('INVITE_CODE', '')
SECURE_COOKIE       = os.environ.get('SECURE_COOKIE', 'true').lower() != 'false'
VAPID_PRIVATE_PEM   = os.environ.get('VAPID_PRIVATE_PEM', '')   # Pfad zur PEM-Datei
VAPID_PUBLIC_KEY    = os.environ.get('VAPID_PUBLIC_KEY', '')     # base64url-kodierter öffentlicher Schlüssel
VAPID_CLAIMS_EMAIL  = os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@example.com')
PUSH_TRIGGER_SECRET = os.environ.get('PUSH_TRIGGER_SECRET', '')

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

def get_user_from_cookie():
    token = request.cookies.get('90tc_session')
    if not token: return None
    row = get_db().execute(
        "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
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

# ── Statische Dateien ─────────────────────────────────────────────────────────
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

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data  = request.get_json(force=True) or {}
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
    try:
        db = get_db()
        db.execute("INSERT INTO users (email, pw_hash) VALUES (?,?)", (email, pw_hash))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'E-Mail bereits registriert'}), 409
    return jsonify({'ok': True}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data  = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password', '')
    row   = get_db().execute("SELECT id, pw_hash FROM users WHERE email=?", (email,)).fetchone()
    if not row or not bcrypt.checkpw(pw.encode(), row['pw_hash'].encode()):
        return jsonify({'error': 'Ungültige Anmeldedaten'}), 401
    token = secrets.token_hex(32)
    db = get_db()
    db.execute("INSERT INTO sessions (token, user_id) VALUES (?,?)", (token, row['id']))
    db.commit()
    resp = make_response(jsonify({'ok': True, 'userId': row['id']}))
    resp.set_cookie('90tc_session', token,
                    httponly=True, secure=SECURE_COOKIE, samesite='Lax',
                    max_age=60*60*24*365)
    return resp

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    token = request.cookies.get('90tc_session')
    db = get_db()
    db.execute("DELETE FROM sessions WHERE token=?", (token,))
    db.commit()
    resp = make_response(jsonify({'ok': True}))
    resp.delete_cookie('90tc_session')
    return resp

@app.route('/api/me')
@login_required
def me():
    return jsonify({'userId': g.user['id'], 'email': g.user['email']})

# ── KV-Sync ───────────────────────────────────────────────────────────────────
@app.route('/api/sync')
@login_required
def sync_get():
    since = int(request.args.get('since', 0))
    rows  = get_db().execute(
        "SELECT key, value, updated_at FROM kv WHERE user_id=? AND updated_at>?",
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
            INSERT INTO kv (user_id, key, value, updated_at) VALUES (?,?,?,?)
            ON CONFLICT(user_id, key) DO UPDATE
              SET value=excluded.value, updated_at=excluded.updated_at
              WHERE excluded.updated_at > kv.updated_at
        """, (g.user['id'], item['key'], json.dumps(item['value']), item['updated_at']))
    db.commit()
    return jsonify({'ok': True, 'written': len(items)})

# ── Web Push ──────────────────────────────────────────────────────────────────
@app.route('/api/vapid-key')
def vapid_key():
    if not VAPID_PUBLIC_KEY:
        return jsonify({'error': 'Push nicht konfiguriert'}), 503
    return jsonify({'publicKey': VAPID_PUBLIC_KEY})

@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(force=True) or {}
    endpoint = data.get('endpoint', '')
    keys     = data.get('keys', {})
    p256dh   = keys.get('p256dh', '')
    auth     = keys.get('auth', '')
    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Ungültige Subscription'}), 400
    db = get_db()
    db.execute("""
        INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?,?,?,?)
        ON CONFLICT(endpoint) DO UPDATE
          SET p256dh=excluded.p256dh, auth=excluded.auth, user_id=excluded.user_id
    """, (g.user['id'], endpoint, p256dh, auth))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/push/subscribe', methods=['DELETE'])
@login_required
def push_unsubscribe():
    data     = request.get_json(force=True) or {}
    endpoint = data.get('endpoint', '')
    if endpoint:
        db = get_db()
        db.execute("DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?",
                   (g.user['id'], endpoint))
        db.commit()
    return jsonify({'ok': True})

@app.route('/api/push/trigger', methods=['POST'])
def push_trigger():
    """Wird jede Minute vom Cron-Job aufgerufen."""
    secret = request.headers.get('X-Push-Secret', '')
    if not PUSH_TRIGGER_SECRET or secret != PUSH_TRIGGER_SECRET:
        return '', 403
    if not PUSH_AVAILABLE or not VAPID_PRIVATE_PEM:
        return jsonify({'ok': True, 'sent': 0, 'reason': 'push not configured'})

    tz_name = 'Europe/Berlin'
    try:
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()
    current_time = now.strftime('%H:%M')

    db = get_db()
    subs = db.execute(
        "SELECT user_id, endpoint, p256dh, auth FROM push_subscriptions"
    ).fetchall()

    sent = 0
    to_delete = []
    for row in subs:
        kv_row = db.execute(
            "SELECT value FROM kv WHERE user_id=? AND key='settings'",
            (row['user_id'],)
        ).fetchone()
        if not kv_row:
            continue
        try:
            settings = json.loads(kv_row['value'])
        except Exception:
            continue
        reminder = settings.get('reminder', {})
        if not reminder.get('enabled') or reminder.get('time') != current_time:
            continue

        payload = json.dumps({
            'title': '90-Tage-Challenge 💪',
            'body':  'Dein Tageseintrag fehlt noch! Bleib dran! 🔥',
            'icon':  '/icon-192.png',
            'badge': '/icon-192.png',
            'tag':   '90tc-daily',
            'url':   '/'
        })
        try:
            webpush(
                subscription_info={
                    'endpoint': row['endpoint'],
                    'keys': {'p256dh': row['p256dh'], 'auth': row['auth']}
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_PEM,
                vapid_claims={'sub': VAPID_CLAIMS_EMAIL}
            )
            sent += 1
        except Exception as ex:
            resp = getattr(ex, 'response', None)
            if resp is not None and resp.status_code in (404, 410):
                to_delete.append(row['endpoint'])

    for ep in to_delete:
        db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))
    if to_delete:
        db.commit()

    return jsonify({'ok': True, 'sent': sent, 'time': current_time})

# ── Analysen ──────────────────────────────────────────────────────────────────
@app.route('/api/analysis', methods=['POST'])
@login_required
def save_analysis():
    d = request.get_json(force=True) or {}
    title = d.get('title', 'Analyse')
    db = get_db()
    db.execute(
        "INSERT INTO analyses (user_id, title, data) VALUES (?,?,?)",
        (g.user['id'], title, json.dumps(d))
    )
    db.commit()
    return jsonify({'ok': True}), 201

@app.route('/api/analysis', methods=['GET'])
@login_required
def get_analyses():
    rows = get_db().execute(
        "SELECT id, created_at, title FROM analyses WHERE user_id=? ORDER BY created_at DESC",
        (g.user['id'],)
    ).fetchall()
    return jsonify([{'id': r['id'], 'created_at': r['created_at'], 'title': r['title']} for r in rows])

@app.route('/api/analysis/<int:analysis_id>', methods=['GET'])
@login_required
def get_analysis(analysis_id):
    row = get_db().execute(
        "SELECT data FROM analyses WHERE id=? AND user_id=?",
        (analysis_id, g.user['id'])
    ).fetchone()
    if not row:
        return jsonify({'error': 'Nicht gefunden'}), 404
    return jsonify(json.loads(row['data']))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
