import os, json, sqlite3, bcrypt, secrets
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, make_response, g

BASE   = os.path.dirname(os.path.abspath(__file__))
DB     = os.path.join(BASE, 'db', '90tc.db')
STATIC = os.path.join(BASE, 'static')

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ['SECRET_KEY']
INVITE_CODE    = os.environ.get('INVITE_CODE', '')

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
                    httponly=True, secure=True, samesite='Lax',
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
