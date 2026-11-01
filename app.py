import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from functools import wraps

import requests
from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-ME-BEFORE-DEPLOYING")

DB_API_URL = os.environ.get("DB_API_URL", "https://p20kng.digamber.in/api/dbp/sql")
DB_API_KEY = os.environ.get("DB_API_KEY", "")
DB_NAME = os.environ.get("DB_NAME", "dbp_2a051213")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def sql_escape(value):
    """Escape a value before placing it in a SQL string literal."""
    return str(value).replace("\\", "\\\\").replace("'", "''")

def run_sql(query):
    if not DB_API_KEY:
        raise RuntimeError("DB_API_KEY is not configured in Render Environment Variables.")
    response = requests.post(
        DB_API_URL,
        json={"db": DB_NAME, "key": DB_API_KEY, "sql": query},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data

def get_rows(data):
    """Accept common JSON result shapes returned by SQL gateway APIs."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "data", "results", "result"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = get_rows(value)
                if nested:
                    return nested
    return []

def ensure_table():
    # Compatible with the licenses table created in the database console.
    run_sql("""
        CREATE TABLE IF NOT EXISTS licenses (
            id SERIAL PRIMARY KEY,
            license_key VARCHAR(100) UNIQUE NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_activations INTEGER DEFAULT 1,
            activation_count INTEGER DEFAULT 0,
            device_id VARCHAR(255)
        );
    """)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

LOGIN_PAGE = """
<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RA J License Admin</title><style>
*{box-sizing:border-box}body{margin:0;background:#080d18;color:#edf2ff;font-family:Arial,sans-serif;display:grid;min-height:100vh;place-items:center;padding:18px}
.card{width:100%;max-width:420px;background:#111a2b;border:1px solid #273650;border-radius:18px;padding:24px;box-shadow:0 15px 50px #0008}
h1{margin:0 0 8px;font-size:25px}.muted{color:#9eacc5;font-size:14px;margin-bottom:22px}
input,button{width:100%;padding:14px;border-radius:10px;margin:7px 0;border:1px solid #34445f;background:#0a1220;color:white;font-size:16px}
button{background:#5b6cff;border:0;font-weight:bold}a{color:#9eafff}.msg{color:#ffb6b6}
</style></head><body><div class="card"><h1>RA J • License Admin</h1><div class="muted">Sign in to manage license keys.</div>
{% with messages=get_flashed_messages() %}{% for m in messages %}<p class="msg">{{m}}</p>{% endfor %}{% endwith %}
<form method="post"><input name="username" placeholder="Admin username" required autocomplete="username">
<input name="password" type="password" placeholder="Admin password" required autocomplete="current-password">
<button type="submit">Login</button></form></div></body></html>
"""

DASHBOARD = """
<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>License Dashboard</title><style>
*{box-sizing:border-box}body{margin:0;background:#080d18;color:#edf2ff;font-family:Arial,sans-serif;padding:18px}
.wrap{max-width:900px;margin:auto}.top,.panel{background:#111a2b;border:1px solid #273650;border-radius:16px;padding:18px;margin-bottom:16px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}h1{font-size:24px;margin:0}h2{font-size:18px;margin-top:0}
input,button{padding:12px;border-radius:9px;border:1px solid #34445f;background:#0a1220;color:white;font-size:15px}
input{width:100%;margin:5px 0 12px}button{background:#5b6cff;border:0;font-weight:bold;cursor:pointer}
.logout{color:#c4ceff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.key{font-family:monospace;overflow-wrap:anywhere;color:#9df5bd}.muted{color:#9eacc5;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:10px;border-bottom:1px solid #293750;overflow-wrap:anywhere}
.tablebox{overflow-x:auto}.flash{color:#a9f2bf}.err{color:#ffaaaa}
</style></head><body><div class="wrap">
<div class="top"><h1>RA J • License Dashboard</h1><a class="logout" href="{{url_for('logout')}}">Logout</a></div>
{% with messages=get_flashed_messages() %}{% for m in messages %}<p class="flash">{{m}}</p>{% endfor %}{% endwith %}
<div class="panel"><h2>Generate License</h2>
<form method="post" action="{{url_for('generate')}}">
<div class="grid"><label>Validity (days)<input name="days" type="number" min="1" max="3650" value="30" required></label>
<label>Max activations<input name="max_activations" type="number" min="1" max="100" value="1" required></label></div>
<button type="submit">Generate Key</button></form>
{% if new_key %}<p>New license key:</p><div class="key">{{new_key}}</div>{% endif %}</div>
<div class="panel"><h2>Recent Licenses</h2>
{% if licenses %}<div class="tablebox"><table><tr><th>Key</th><th>Status</th><th>Expires</th><th>Activations</th></tr>
{% for item in licenses %}<tr><td class="key">{{item.get('license_key','')}}</td><td>{{item.get('status','')}}</td><td>{{item.get('expires_at','')}}</td><td>{{item.get('activation_count','')}} / {{item.get('max_activations','')}}</td></tr>{% endfor %}</table></div>
{% else %}<p class="muted">No license rows were returned yet. Check that the SQL API returns SELECT results in JSON.</p>{% endif %}
</div>
<div class="panel"><h2>Public verification API</h2><p class="muted">POST /api/verify with JSON: {"license_key":"YOUR-KEY","device_id":"DEVICE-001"}</p></div>
</div></body></html>
"""

@app.route("/")
def home():
    return """<main style='font-family:Arial;background:#080d18;color:white;min-height:100vh;padding:35px'>
    <h1>RA J License System</h1><p>License verification service is online.</p>
    <p><a style='color:#aab7ff' href='/admin/login'>Admin login</a></p></main>"""

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            flash("Set ADMIN_USERNAME and ADMIN_PASSWORD in Render Environment Variables.")
        elif secrets.compare_digest(request.form.get("username", ""), ADMIN_USERNAME) and secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Username or password is incorrect.")
    return render_template_string(LOGIN_PAGE)

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def dashboard():
    new_key = session.pop("new_key", None)
    try:
        result = run_sql("SELECT license_key, status, expires_at, max_activations, activation_count FROM licenses ORDER BY id DESC LIMIT 50;")
        licenses = get_rows(result)
    except Exception as exc:
        flash("Database read error: " + str(exc))
        licenses = []
    return render_template_string(DASHBOARD, licenses=licenses, new_key=new_key)

@app.route("/admin/generate", methods=["POST"])
@admin_required
def generate():
    try:
        days = int(request.form.get("days", "30"))
        max_activations = int(request.form.get("max_activations", "1"))
        if not (1 <= days <= 3650 and 1 <= max_activations <= 100):
            raise ValueError("Days must be 1–3650 and activations 1–100.")
        alphabet = string.ascii_uppercase + string.digits
        raw = "".join(secrets.choice(alphabet) for _ in range(16))
        key = "RAJ-" + "-".join(raw[i:i+4] for i in range(0, 16, 4))
        expires = (datetime.now(timezone.utc) + timedelta(days=days)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        run_sql(
            "INSERT INTO licenses (license_key, status, expires_at, max_activations, activation_count) VALUES "
            f"('{sql_escape(key)}', 'active', '{sql_escape(expires)}', {max_activations}, 0);"
        )
        session["new_key"] = key
        flash("License created.")
    except Exception as exc:
        flash("Could not create license: " + str(exc))
    return redirect(url_for("dashboard"))

@app.route("/api/verify", methods=["POST"])
def verify():
    body = request.get_json(silent=True) or {}
    key = str(body.get("license_key", "")).strip().upper()
    device = str(body.get("device_id", "")).strip()
    if not key or not device or len(key) > 100 or len(device) > 255:
        return jsonify(ok=False, message="license_key and device_id are required."), 400
    try:
        rows = get_rows(run_sql(
            "SELECT license_key, status, expires_at, max_activations, activation_count, device_id "
            f"FROM licenses WHERE license_key = '{sql_escape(key)}' LIMIT 1;"
        ))
        if not rows:
            return jsonify(ok=False, message="License not found."), 404
        item = rows[0]
        if str(item.get("status", "")).lower() != "active":
            return jsonify(ok=False, message="License is not active."), 403
        expiry = item.get("expires_at")
        if expiry:
            expiry_text = str(expiry).replace("Z", "+00:00")
            try:
                exp = datetime.fromisoformat(expiry_text)
                now = datetime.now(exp.tzinfo) if exp.tzinfo else datetime.now()
                if exp <= now:
                    return jsonify(ok=False, message="License expired."), 403
            except ValueError:
                return jsonify(ok=False, message="Invalid expiry date in database."), 500
        old_device = item.get("device_id")
        count = int(item.get("activation_count") or 0)
        maximum = int(item.get("max_activations") or 1)
        if old_device and str(old_device) != device:
            if count >= maximum:
                return jsonify(ok=False, message="Activation limit reached."), 403
            run_sql(
                "UPDATE licenses SET activation_count = activation_count + 1, "
                f"device_id = '{sql_escape(device)}' WHERE license_key = '{sql_escape(key)}';"
            )
        elif not old_device:
            run_sql(
                "UPDATE licenses SET activation_count = 1, "
                f"device_id = '{sql_escape(device)}' WHERE license_key = '{sql_escape(key)}';"
            )
        return jsonify(ok=True, message="License verified.", license_key=key)
    except Exception as exc:
        app.logger.exception("Verification failed")
        return jsonify(ok=False, message="Database/API error. Check server logs and SQL API response."), 502

@app.route("/health")
def health():
    return jsonify(ok=True, service="RA J License System")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
