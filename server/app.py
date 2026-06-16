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
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')

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
        "",
        f"## Übersicht",
        f"- Tag {m.get('dayN','?')} von {m.get('dur','90')} | Logging-Rate {m.get('logRate','?')}% | Compliance-Score {sc.get('avg','—')}%",
    ]

    if w.get('start'):
        lines += [
            "", "## Gewicht",
            f"- Start {w['start']} kg → Aktuell {w.get('current','—')} kg (Δ {w.get('delta','—')} kg)",
            f"- Wöchentliche Rate: {w.get('weeklyRate','—')} kg/Woche",
        ]
        if w.get('prediction'):
            lines.append(f"- Prognose Challengeende: {w['prediction']} kg")

    nt = n.get('targets', {})
    if n.get('avgKal'):
        nd = n.get('nutDays', 1) or 1
        kp = round(n.get('kalCmp', 0) / nd * 100)
        pp = round(n.get('proCmp', 0) / nd * 100)
        lines += [
            "", "## Ernährung",
            f"- Ø Kalorien {n['avgKal']} kcal (Ziel {nt.get('kalorien','—')}), Kalorienplan {kp}% der Tage eingehalten",
            f"- Ø Protein {n.get('avgPro','—')} g (Ziel {nt.get('protein','—')} g), Ziel {pp}% erreicht",
            f"- Ø Fett {n.get('avgFat','—')} g | Ø KH {n.get('avgKh','—')} g",
            f"- Konsistenz (Stabw. Kcal): ±{n.get('kalStd','—')} kcal",
        ]
        if n.get('empirTDEE'):
            lines.append(f"- Empirischer TDEE (aus Daten): {n['empirTDEE']} kcal/Tag")
        if n.get('formulaTDEE'):
            lines.append(f"- Mifflin-TDEE (Formel): {n['formulaTDEE']} kcal/Tag")

    if tr.get('trDone', 0) > 0:
        lines += [
            "", "## Training",
            f"- Durchgeführt {tr.get('trDone','—')}× von {tr.get('trPlan','—')} geplant ({tr.get('trCmp','—')}%)",
            f"- Trainingsfortschritt erreicht: {tr.get('trProgRate','—')}% | Längste Streak {tr.get('maxStreak','—')} Tage",
        ]

    if rc.get('avgSl'):
        tg = rc.get('targets', {})
        lines += [
            "", "## Erholung & Lifestyle",
            f"- Ø Schlaf {rc['avgSl']} h (Ziel {tg.get('schlaf',7)} h)",
            f"- Ø Schritte {rc.get('avgSt','—')} (Ziel {tg.get('schritte',10000)})",
            f"- Ø Wasser {rc.get('avgWa','—')} L (Ziel {tg.get('wasser',2.5)} L)",
        ]

    sl = c.get('slTr', {})
    pr = c.get('prPr', {})
    corr_lines = []
    if sl.get('gT', 0) >= 3 or sl.get('bT', 0) >= 3:
        gP = round(sl['g']/sl['gT']*100) if sl.get('gT') else '—'
        bP = round(sl['b']/sl['bT']*100) if sl.get('bT') else '—'
        corr_lines.append(f"- Schlaf → Training Folgetag: {gP}% (guter Schlaf) vs. {bP}% (schlechter Schlaf)")
    if pr.get('gT', 0) >= 3 or pr.get('bT', 0) >= 3:
        gP = round(pr['g']/pr['gT']*100) if pr.get('gT') else '—'
        bP = round(pr['b']/pr['bT']*100) if pr.get('bT') else '—'
        corr_lines.append(f"- Protein → Trainingsfortschritt: {gP}% (ausreichend Protein) vs. {bP}% (zu wenig)")
    if corr_lines:
        lines += ["", "## Zusammenhänge"] + corr_lines

    mkeys = ['schulter','brust','rechterArm','linkerArm','ueber5','nabel','unter5','huefte','rechtsBein','linksBein']
    mlbls = {'schulter':'Schulter','brust':'Brust','rechterArm':'Rechter Arm','linkerArm':'Linker Arm',
             'ueber5':'Über Nabel','nabel':'Nabel','unter5':'Unter Nabel','huefte':'Hüfte',
             'rechtsBein':'Rechtes Bein','linksBein':'Linkes Bein'}
    ms = meas.get('start', {}) or {}
    ml = meas.get('latest', {}) or {}
    meas_lines = []
    for k in mkeys:
        s, l = ms.get(k), ml.get(k)
        if s or l:
            dt = f" (Δ {'+' if l-s>0 else ''}{round(l-s,1)} cm)" if s and l else ""
            meas_lines.append(f"- {mlbls[k]}: {s or '—'} → {l or '—'} cm{dt}")
    if meas_lines:
        lines += ["", "## Körperumfänge"] + meas_lines

    lines += [
        "", "---",
        "Bitte erstelle einen strukturierten deutschen Bericht mit diesen 6 Abschnitten:",
        "1. **Ernährung** — Kalorienverteilung, Makros, Konsistenz; Bezug auf aktuelle Studien (z.B. Proteinempfehlung 1,6–2,2 g/kg)",
        "2. **Körperumfänge & Komposition** — Was die Messwerte über Fett- vs. Muskelmasse aussagen",
        "3. **Training** — Regelmäßigkeit, Progression, Streak; Einordnung nach Trainingswissenschaft",
        "4. **Erholung & Lifestyle** — Schlaf, NEAT, Hydration und ihr Einfluss auf Erfolg (wissenschaftlich belegt)",
        "5. **Zusammenhänge** — Interpretation der Korrelationen, was sie für diesen Nutzer bedeuten",
        "6. **Empfehlungen** — 3–5 konkrete, priorisierte Maßnahmen für die verbleibende Zeit",
        "Schreibe direkt, motivierend und ehrlich. Verwende Markdown (##, **, - Listen). Keine Disclaimer.",
    ]
    return '\n'.join(lines)

@app.route('/api/ai-report', methods=['POST'])
@login_required
def ai_report():
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'KI-Bericht nicht konfiguriert — ANTHROPIC_API_KEY fehlt in der .env auf dem Server'}), 503
    data = request.get_json(force=True) or {}
    prompt = _build_ai_prompt(data)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = ''.join(getattr(b, 'text', '') for b in resp.content)
        return jsonify({'ok': True, 'report': text})
    except Exception as e:
        return jsonify({'error': f'API-Fehler: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
