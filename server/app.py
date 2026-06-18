import os, json, sqlite3, bcrypt, secrets, shutil
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
VAPID_PRIVATE_PEM   = os.environ.get('VAPID_PRIVATE_PEM', '')
VAPID_PUBLIC_KEY    = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_EMAIL  = os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@example.com')
PUSH_TRIGGER_SECRET = os.environ.get('PUSH_TRIGGER_SECRET', '')
# Env-Fallback-Keys (DB-Keys haben Vorrang)
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY      = os.environ.get('OPENAI_API_KEY', '')
GOOGLE_API_KEY      = os.environ.get('GOOGLE_API_KEY', '')
# Bootstrap: diese E-Mail wird beim ersten Login/Register automatisch Admin
ADMIN_EMAIL         = os.environ.get('ADMIN_EMAIL', '').strip().lower()

VALID_MODELS = [
    'claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8',
    'gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini',
    'gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.5-pro',
]
MODEL_PRICES = {
    'claude-haiku-4-5-20251001': (1.0,  5.0),
    'claude-sonnet-4-6':         (3.0, 15.0),
    'claude-opus-4-8':           (5.0, 25.0),
    'gpt-4o-mini':               (0.15, 0.60),
    'gpt-4o':                    (2.50, 10.0),
    'gpt-4.1-mini':              (0.40,  1.60),
    'gemini-2.0-flash':          (0.10,  0.40),
    'gemini-2.5-flash':          (0.30,  2.50),
    'gemini-2.5-pro':            (1.25, 10.0),
}

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
    return get_db().execute(
        "SELECT u.id, u.email, u.username, u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
        (token,)
    ).fetchone()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_cookie()
        if not user:
            return jsonify({'error': 'nicht angemeldet'}), 401
        g.user = user
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_cookie()
        if not user:
            return jsonify({'error': 'nicht angemeldet'}), 401
        if not user['is_admin']:
            return jsonify({'error': 'Kein Admin-Zugriff'}), 403
        g.user = user
        return f(*args, **kwargs)
    return wrapper

def get_config(key, default=None):
    row = get_db().execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default

def set_config(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    db.commit()

def get_api_key(provider):
    """DB-Key hat Vorrang vor env-Variable."""
    db_key = get_config(f'{provider}_api_key', '')
    if db_key:
        return db_key
    return {'anthropic': ANTHROPIC_API_KEY, 'openai': OPENAI_API_KEY, 'google': GOOGLE_API_KEY}.get(provider, '')

def calc_cost(model, inp, out):
    p = MODEL_PRICES.get(model, (0, 0))
    return round((inp * p[0] + out * p[1]) / 1_000_000, 8)

def bootstrap_admin(user_id, email):
    """Setzt is_admin=1 wenn Email mit ADMIN_EMAIL übereinstimmt."""
    if ADMIN_EMAIL and email.lower() == ADMIN_EMAIL:
        get_db().execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))

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
    data     = request.get_json(force=True) or {}
    email    = (data.get('email') or '').strip().lower()
    pw       = data.get('password', '')
    code     = data.get('invite_code', '')
    username = (data.get('username') or '').strip()
    if INVITE_CODE and code != INVITE_CODE:
        return jsonify({'error': 'Ungültiger Einladungscode'}), 403
    if not email or '@' not in email:
        return jsonify({'error': 'Ungültige E-Mail'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Passwort zu kurz (min. 8 Zeichen)'}), 400
    if not username:
        return jsonify({'error': 'Benutzername erforderlich'}), 400
    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        db = get_db()
        cur = db.execute(
            "INSERT INTO users (email, pw_hash, username) VALUES (?,?,?)",
            (email, pw_hash, username)
        )
        new_id = cur.lastrowid
        bootstrap_admin(new_id, email)
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'E-Mail bereits registriert'}), 409
    return jsonify({'ok': True}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data  = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password', '')
    row   = get_db().execute(
        "SELECT id, pw_hash FROM users WHERE email=?", (email,)
    ).fetchone()
    if not row or not bcrypt.checkpw(pw.encode(), row['pw_hash'].encode()):
        return jsonify({'error': 'Ungültige Anmeldedaten'}), 401
    db = get_db()
    bootstrap_admin(row['id'], email)
    db.commit()
    token = secrets.token_hex(32)
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
    u = g.user
    return jsonify({
        'userId':   u['id'],
        'email':    u['email'],
        'username': u['username'] or '',
        'isAdmin':  bool(u['is_admin']),
    })

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
    data   = request.get_json(force=True) or {}
    endpoint = data.get('endpoint', '')
    keys   = data.get('keys', {})
    p256dh = keys.get('p256dh', '')
    auth   = keys.get('auth', '')
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
    secret = request.headers.get('X-Push-Secret', '')
    if not PUSH_TRIGGER_SECRET or secret != PUSH_TRIGGER_SECRET:
        return '', 403
    if not PUSH_AVAILABLE or not VAPID_PRIVATE_PEM:
        return jsonify({'ok': True, 'sent': 0, 'reason': 'push not configured'})
    try:
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo('Europe/Berlin'))
    except Exception:
        now = datetime.now()
    current_time = now.strftime('%H:%M')
    db = get_db()
    subs = db.execute("SELECT user_id, endpoint, p256dh, auth FROM push_subscriptions").fetchall()
    sent, to_delete = 0, []
    for row in subs:
        kv_row = db.execute("SELECT value FROM kv WHERE user_id=? AND key='settings'", (row['user_id'],)).fetchone()
        if not kv_row: continue
        try: settings = json.loads(kv_row['value'])
        except: continue
        reminder = settings.get('reminder', {})
        if not reminder.get('enabled') or reminder.get('time') != current_time: continue
        payload = json.dumps({'title':'90-Tage-Challenge 💪','body':'Dein Tageseintrag fehlt noch! Bleib dran! 🔥',
                              'icon':'/icon-192.png','badge':'/icon-192.png','tag':'90tc-daily','url':'/'})
        try:
            webpush(subscription_info={'endpoint':row['endpoint'],'keys':{'p256dh':row['p256dh'],'auth':row['auth']}},
                    data=payload, vapid_private_key=VAPID_PRIVATE_PEM, vapid_claims={'sub':VAPID_CLAIMS_EMAIL})
            sent += 1
        except Exception as ex:
            resp = getattr(ex, 'response', None)
            if resp is not None and resp.status_code in (404, 410):
                to_delete.append(row['endpoint'])
    for ep in to_delete:
        db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))
    if to_delete: db.commit()
    return jsonify({'ok': True, 'sent': sent, 'time': current_time})

# ── Analysen ──────────────────────────────────────────────────────────────────
@app.route('/api/analysis', methods=['POST'])
@login_required
def save_analysis():
    d = request.get_json(force=True) or {}
    db = get_db()
    db.execute("INSERT INTO analyses (user_id, title, data) VALUES (?,?,?)",
               (g.user['id'], d.get('title', 'Analyse'), json.dumps(d)))
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
    if not row: return jsonify({'error': 'Nicht gefunden'}), 404
    return jsonify(json.loads(row['data']))

# ── Admin-Bereich ─────────────────────────────────────────────────────────────
@app.route('/api/admin/status')
@admin_required
def admin_status():
    db = get_db()
    db_size_kb   = round(os.path.getsize(DB) / 1024, 1) if os.path.exists(DB) else 0
    backup_dir   = os.path.join(BASE, 'db', 'backups')
    backup_files = sorted(os.listdir(backup_dir)) if os.path.isdir(backup_dir) else []
    return jsonify({
        'users':              db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'sessions':           db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
        'kv_entries':         db.execute("SELECT COUNT(*) FROM kv").fetchone()[0],
        'analyses':           db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0],
        'push_subscriptions': db.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0],
        'ai_reports':         db.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0],
        'db_size_kb':         db_size_kb,
        'last_backup':        backup_files[-1] if backup_files else None,
        'ai_model':           get_config('ai_model', 'claude-haiku-4-5-20251001'),
        'api_keys': {
            'anthropic': bool(get_api_key('anthropic')),
            'openai':    bool(get_api_key('openai')),
            'google':    bool(get_api_key('google')),
        }
    })

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    db = get_db()
    users = db.execute("SELECT id, email, username, is_admin, created_at FROM users ORDER BY created_at").fetchall()
    result = []
    for u in users:
        result.append({
            'id':         u['id'],
            'email':      u['email'],
            'username':   u['username'] or '',
            'is_admin':   bool(u['is_admin']),
            'created_at': u['created_at'],
            'kv_entries': db.execute("SELECT COUNT(*) FROM kv WHERE user_id=?", (u['id'],)).fetchone()[0],
            'sessions':   db.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?", (u['id'],)).fetchone()[0],
            'analyses':   db.execute("SELECT COUNT(*) FROM analyses WHERE user_id=?", (u['id'],)).fetchone()[0],
        })
    return jsonify(result)

@app.route('/api/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    data     = request.get_json(force=True) or {}
    email    = (data.get('email') or '').strip().lower()
    pw       = data.get('password', '')
    username = (data.get('username') or '').strip()
    is_admin = bool(data.get('is_admin', False))
    if not email or '@' not in email:
        return jsonify({'error': 'Ungültige E-Mail'}), 400
    if len(pw) < 8:
        return jsonify({'error': 'Passwort zu kurz (min. 8 Zeichen)'}), 400
    if not username:
        return jsonify({'error': 'Benutzername erforderlich'}), 400
    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        db = get_db()
        db.execute("INSERT INTO users (email, pw_hash, username, is_admin) VALUES (?,?,?,?)",
                   (email, pw_hash, username, 1 if is_admin else 0))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'E-Mail bereits registriert'}), 409
    return jsonify({'ok': True}), 201

@app.route('/api/admin/users/<int:user_id>', methods=['PATCH'])
@admin_required
def admin_patch_user(user_id):
    data   = request.get_json(force=True) or {}
    action = data.get('action')
    db     = get_db()
    if action == 'toggle_admin':
        if user_id == g.user['id']:
            return jsonify({'error': 'Eigene Admin-Rechte nicht änderbar'}), 400
        row = db.execute("SELECT is_admin FROM users WHERE id=?", (user_id,)).fetchone()
        if not row: return jsonify({'error': 'Nutzer nicht gefunden'}), 404
        db.execute("UPDATE users SET is_admin=? WHERE id=?", (0 if row['is_admin'] else 1, user_id))
        db.commit()
        return jsonify({'ok': True, 'is_admin': not row['is_admin']})
    elif action == 'reset_password':
        pw = data.get('password', '')
        if len(pw) < 8:
            return jsonify({'error': 'Passwort zu kurz (min. 8 Zeichen)'}), 400
        pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        db.execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, user_id))
        db.commit()
        return jsonify({'ok': True})
    return jsonify({'error': 'Unbekannte Aktion'}), 400

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    if user_id == g.user['id']:
        return jsonify({'error': 'Eigenen Account nicht löschbar'}), 400
    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/admin/analyses')
@admin_required
def admin_analyses():
    rows = get_db().execute("""
        SELECT a.id, a.created_at, a.title, u.email, u.username,
               json_extract(a.data, '$.score.avg') as score,
               json_extract(a.data, '$.meta.dayN') as day_n,
               json_extract(a.data, '$.meta.logRate') as log_rate
        FROM analyses a JOIN users u ON u.id=a.user_id
        ORDER BY a.created_at DESC
    """).fetchall()
    return jsonify([{
        'id': r['id'], 'created_at': r['created_at'], 'title': r['title'],
        'email': r['email'], 'username': r['username'] or '',
        'score': r['score'], 'day_n': r['day_n'], 'log_rate': r['log_rate'],
    } for r in rows])

@app.route('/api/admin/config', methods=['GET'])
@admin_required
def admin_config_get():
    return jsonify({'ai_model': get_config('ai_model', 'claude-haiku-4-5-20251001')})

@app.route('/api/admin/config', methods=['POST'])
@admin_required
def admin_config_set():
    data  = request.get_json(force=True) or {}
    model = data.get('ai_model', '').strip()
    if model not in VALID_MODELS:
        return jsonify({'error': 'Unbekanntes Modell'}), 400
    set_config('ai_model', model)
    return jsonify({'ok': True})

@app.route('/api/admin/api-keys', methods=['GET'])
@admin_required
def admin_api_keys_get():
    return jsonify({
        'anthropic': bool(get_api_key('anthropic')),
        'openai':    bool(get_api_key('openai')),
        'google':    bool(get_api_key('google')),
    })

@app.route('/api/admin/api-keys', methods=['POST'])
@admin_required
def admin_api_keys_set():
    data = request.get_json(force=True) or {}
    for provider in ('anthropic', 'openai', 'google'):
        key = data.get(provider, '').strip()
        if key:
            set_config(f'{provider}_api_key', key)
    return jsonify({'ok': True})

@app.route('/api/admin/ai-usage')
@admin_required
def admin_ai_usage():
    days = request.args.get('days', 'all')
    where = ''
    if days == '7':
        where = "WHERE a.created_at >= datetime('now', '-7 days')"
    elif days == '30':
        where = "WHERE a.created_at >= datetime('now', '-30 days')"
    rows = get_db().execute(f"""
        SELECT u.id as user_id, u.username, u.email, a.model,
               SUM(a.input_tokens) as inp, SUM(a.output_tokens) as out,
               SUM(a.cost_usd) as cost, COUNT(*) as calls
        FROM ai_usage a JOIN users u ON u.id=a.user_id
        {where}
        GROUP BY u.id, a.model
        ORDER BY u.id, a.model
    """).fetchall()
    result = {}
    for r in rows:
        uid = r['user_id']
        if uid not in result:
            result[uid] = {'username': r['username'] or r['email'], 'email': r['email'], 'models': []}
        result[uid]['models'].append({
            'model': r['model'], 'calls': r['calls'],
            'input_tokens': r['inp'], 'output_tokens': r['out'],
            'cost_usd': round(r['cost'], 6),
        })
    return jsonify(list(result.values()))

@app.route('/api/admin/ai-test', methods=['POST'])
@admin_required
def admin_ai_test():
    data  = request.get_json(force=True) or {}
    model = data.get('model', get_config('ai_model', 'claude-haiku-4-5-20251001'))
    if model not in VALID_MODELS:
        return jsonify({'error': 'Unbekanntes Modell'}), 400
    prompt = 'Antworte nur mit dem Wort "OK".'
    try:
        inp_tok = out_tok = 0
        if model.startswith('claude-'):
            key = get_api_key('anthropic')
            if not key: return jsonify({'error': 'Anthropic API-Key fehlt'}), 503
            import anthropic
            r = anthropic.Anthropic(api_key=key).messages.create(
                model=model, max_tokens=10, messages=[{'role':'user','content':prompt}])
            text = ''.join(getattr(b,'text','') for b in r.content)
            inp_tok = r.usage.input_tokens; out_tok = r.usage.output_tokens
        elif model.startswith('gpt-'):
            key = get_api_key('openai')
            if not key: return jsonify({'error': 'OpenAI API-Key fehlt'}), 503
            import openai
            r = openai.OpenAI(api_key=key).chat.completions.create(
                model=model, max_tokens=10, messages=[{'role':'user','content':prompt}])
            text = r.choices[0].message.content
            inp_tok = r.usage.prompt_tokens; out_tok = r.usage.completion_tokens
        elif model.startswith('gemini-'):
            key = get_api_key('google')
            if not key: return jsonify({'error': 'Google API-Key fehlt'}), 503
            import google.generativeai as genai
            genai.configure(api_key=key)
            rg = genai.GenerativeModel(model).generate_content(prompt)
            text = rg.text
            if hasattr(rg,'usage_metadata'):
                inp_tok = rg.usage_metadata.prompt_token_count or 0
                out_tok = rg.usage_metadata.candidates_token_count or 0
        else:
            return jsonify({'error': 'Unbekanntes Modell'}), 400
        return jsonify({'ok': True, 'response': text.strip(), 'model': model,
                        'input_tokens': inp_tok, 'output_tokens': out_tok})
    except ImportError as e:
        return jsonify({'error': f'Bibliothek nicht installiert: {e}'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/backup', methods=['POST'])
@admin_required
def admin_backup():
    backup_dir = os.path.join(BASE, 'db', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts   = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    dest = os.path.join(backup_dir, f'90tc-{ts}-manual.db')
    shutil.copy2(DB, dest)
    return jsonify({'ok': True, 'file': os.path.basename(dest)})

# ── KI-Bericht ────────────────────────────────────────────────────────────────
def _build_ai_prompt(data):
    m  = data.get('meta', {})
    w  = data.get('weight', {})
    n  = data.get('nutrition', {})
    tr = data.get('training', {})
    rc = data.get('recovery', {})
    c  = data.get('correlations', {})
    sc = data.get('score', {})
    meas = data.get('measurements', {})
    lines = [
        "Erstelle einen wissenschaftlich fundierten, persönlichen Fitness- und Gesundheitsbericht für folgende Challenge-Daten:",
        "", "## Übersicht",
        f"- Tag {m.get('dayN','?')} von {m.get('dur','90')} | Logging-Rate {m.get('logRate','?')}% | Compliance-Score {sc.get('avg','—')}%",
    ]
    if w.get('start'):
        lines += ["","## Gewicht",
            f"- Start {w['start']} kg → Aktuell {w.get('current','—')} kg (Δ {w.get('delta','—')} kg)",
            f"- Wöchentliche Rate: {w.get('weeklyRate','—')} kg/Woche"]
        if w.get('prediction'): lines.append(f"- Prognose: {w['prediction']} kg")
    nt = n.get('targets', {})
    if n.get('avgKal'):
        nd = n.get('nutDays',1) or 1
        kp = round(n.get('kalCmp',0)/nd*100); pp = round(n.get('proCmp',0)/nd*100)
        lines += ["","## Ernährung",
            f"- Ø Kalorien {n['avgKal']} kcal (Ziel {nt.get('kalorien','—')}), Kalorienplan {kp}% eingehalten",
            f"- Ø Protein {n.get('avgPro','—')} g (Ziel {nt.get('protein','—')} g), Ziel {pp}% erreicht",
            f"- Ø Fett {n.get('avgFat','—')} g | Ø KH {n.get('avgKh','—')} g | Konsistenz ±{n.get('kalStd','—')} kcal"]
        if n.get('empirTDEE'): lines.append(f"- Empir. TDEE: {n['empirTDEE']} kcal/Tag")
        if n.get('formulaTDEE'): lines.append(f"- Mifflin-TDEE: {n['formulaTDEE']} kcal/Tag")
    if tr.get('trDone',0)>0:
        lines += ["","## Training",
            f"- {tr.get('trDone','—')}× von {tr.get('trPlan','—')} geplant ({tr.get('trCmp','—')}%)",
            f"- Progression {tr.get('trProgRate','—')}% | Streak {tr.get('maxStreak','—')} Tage"]
    if rc.get('avgSl'):
        tg = rc.get('targets',{})
        lines += ["","## Erholung & Lifestyle",
            f"- Ø Schlaf {rc['avgSl']} h (Ziel {tg.get('schlaf',7)} h)",
            f"- Ø Schritte {rc.get('avgSt','—')} | Ø Wasser {rc.get('avgWa','—')} L"]
    sl = c.get('slTr',{}); pr = c.get('prPr',{})
    corr = []
    if sl.get('gT',0)>=3 or sl.get('bT',0)>=3:
        gP=round(sl['g']/sl['gT']*100) if sl.get('gT') else '—'
        bP=round(sl['b']/sl['bT']*100) if sl.get('bT') else '—'
        corr.append(f"- Schlaf→Training: {gP}% (gut) vs {bP}% (schlecht)")
    if pr.get('gT',0)>=3 or pr.get('bT',0)>=3:
        gP=round(pr['g']/pr['gT']*100) if pr.get('gT') else '—'
        bP=round(pr['b']/pr['bT']*100) if pr.get('bT') else '—'
        corr.append(f"- Protein→Progression: {gP}% (ausreichend) vs {bP}% (zu wenig)")
    if corr: lines += ["","## Zusammenhänge"]+corr
    mkeys = ['schulter','brust','rechterArm','linkerArm','ueber5','nabel','unter5','huefte','rechtsBein','linksBein']
    mlbls = {'schulter':'Schulter','brust':'Brust','rechterArm':'Rechter Arm','linkerArm':'Linker Arm',
             'ueber5':'Über Nabel','nabel':'Nabel','unter5':'Unter Nabel','huefte':'Hüfte',
             'rechtsBein':'Rechtes Bein','linksBein':'Linkes Bein'}
    ms = meas.get('start',{}) or {}; ml = meas.get('latest',{}) or {}
    ml_lines = []
    for k in mkeys:
        s, l = ms.get(k), ml.get(k)
        if s or l:
            dt = f" (Δ {'+' if l-s>0 else ''}{round(l-s,1)} cm)" if s and l else ""
            ml_lines.append(f"- {mlbls[k]}: {s or '—'} → {l or '—'} cm{dt}")
    if ml_lines: lines += ["","## Körperumfänge"]+ml_lines
    lines += ["","---",
        "Bitte erstelle einen strukturierten deutschen Bericht mit diesen 6 Abschnitten:",
        "1. **Ernährung** — Makros, Konsistenz, Studien (Protein 1,6–2,2 g/kg)",
        "2. **Körperumfänge & Komposition** — Fett- vs. Muskelmasse",
        "3. **Training** — Regelmäßigkeit, Progression, Streak",
        "4. **Erholung & Lifestyle** — Schlaf, NEAT, Hydration",
        "5. **Zusammenhänge** — Korrelationen interpretieren",
        "6. **Empfehlungen** — 3–5 konkrete Maßnahmen",
        "Direkt, motivierend, ehrlich. Markdown (##, **, Listen). Keine Disclaimer."]
    return '\n'.join(lines)

@app.route('/api/ai-report', methods=['POST'])
@login_required
def ai_report():
    model  = get_config('ai_model', 'claude-haiku-4-5-20251001')
    data   = request.get_json(force=True) or {}
    prompt = _build_ai_prompt(data)
    inp_tok = out_tok = 0
    try:
        if model.startswith('claude-'):
            key = get_api_key('anthropic')
            if not key: return jsonify({'error': 'ANTHROPIC_API_KEY nicht konfiguriert'}), 503
            import anthropic
            resp = anthropic.Anthropic(api_key=key).messages.create(
                model=model, max_tokens=2500, messages=[{'role':'user','content':prompt}])
            text = ''.join(getattr(b,'text','') for b in resp.content)
            inp_tok = resp.usage.input_tokens; out_tok = resp.usage.output_tokens
        elif model.startswith('gpt-'):
            key = get_api_key('openai')
            if not key: return jsonify({'error': 'OPENAI_API_KEY nicht konfiguriert'}), 503
            import openai
            resp = openai.OpenAI(api_key=key).chat.completions.create(
                model=model, max_tokens=2500, messages=[{'role':'user','content':prompt}])
            text = resp.choices[0].message.content
            inp_tok = resp.usage.prompt_tokens; out_tok = resp.usage.completion_tokens
        elif model.startswith('gemini-'):
            key = get_api_key('google')
            if not key: return jsonify({'error': 'GOOGLE_API_KEY nicht konfiguriert'}), 503
            import google.generativeai as genai
            genai.configure(api_key=key)
            resp = genai.GenerativeModel(model).generate_content(prompt)
            text = resp.text
            try: inp_tok = resp.usage_metadata.prompt_token_count; out_tok = resp.usage_metadata.candidates_token_count
            except: inp_tok = len(prompt)//4; out_tok = len(text)//4
        else:
            return jsonify({'error': f'Unbekanntes Modell: {model}'}), 400
        # Usage loggen
        cost = calc_cost(model, inp_tok, out_tok)
        db = get_db()
        db.execute("INSERT INTO ai_usage (user_id, model, input_tokens, output_tokens, cost_usd) VALUES (?,?,?,?,?)",
                   (g.user['id'], model, inp_tok, out_tok, cost))
        db.commit()
        return jsonify({'ok': True, 'report': text, 'model': model,
                        'tokens': {'input': inp_tok, 'output': out_tok}, 'cost_usd': cost})
    except ImportError as e:
        return jsonify({'error': f'Bibliothek nicht installiert: {e}'}), 503
    except Exception as e:
        return jsonify({'error': f'API-Fehler: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
