import os, time, sqlite3, requests, schedule, smtplib, openai
from threading import Thread
from flask import Flask, request, redirect, jsonify, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SECRET_KEY = os.getenv("SECRET_KEY", "secret")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_TOKEN = os.getenv("API_TOKEN")

DB_PATH = "logs.db"
app = Flask(__name__)
app.secret_key = SECRET_KEY
openai.api_key = OPENAI_API_KEY

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, source TEXT, message TEXT, timestamp TEXT)")
    try: c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", generate_password_hash("pass123"), "admin"))
    except: pass
    conn.commit()
    conn.close()

def save_log(source, message):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO logs (source, message, timestamp) VALUES (?, ?, ?)", (source, message, ts))
    conn.commit()
    conn.close()
    if "ALERT" in message.upper():
        send_email("🚨 Alert Triggered", f"[{source}] {message}")

def fetch_logs():
    conn = sqlite3.connect(DB_PATH)
    logs = conn.execute("SELECT source, message, timestamp FROM logs").fetchall()
    conn.close()
    return logs

def summarize_logs():
    logs = fetch_logs()
    today_logs = [f"[{s}] {m}" for s, m, t in logs if t.startswith(str(date.today()))]
    if not today_logs: return "No logs today."
    prompt = "Summarize:\n" + "\n".join(today_logs)
    try:
        res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
        return res.choices[0].message.content
    except Exception as e:
        return f"Summary error: {e}"

def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_USER, EMAIL_RECEIVER
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as s:
            s.starttls(); s.login(EMAIL_USER, EMAIL_PASS)
            s.sendmail(msg["From"], [EMAIL_RECEIVER], msg.as_string())
    except Exception as e: print("Email error:", e)

def telegram_bot():
    last_id = None
    while True:
        try:
            response = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
            data = response.json()
            updates = data.get("result", [])
        except Exception as e:
            print("Bot error:", e)
            updates = []

        for u in updates:
            uid = u.get("update_id")
            if last_id is None or uid > last_id:
                last_id = uid
                msg = u.get("message", {}).get("text", "")
                chat = u.get("message", {}).get("chat", {}).get("id")
                if msg.startswith("/log"):
                    content = msg[4:].strip()
                    save_log("TELEGRAM", content)
                    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                 params={"chat_id": chat, "text": f"✅ Logged: {content}"})
                elif msg.startswith("/stats"):
                    logs = fetch_logs()
                    total = len(logs)
                    srcs = {}
                    for s, _, _ in logs:
                        srcs[s] = srcs.get(s, 0) + 1
                    txt = f"📊 Total: {total}\n" + "\n".join([f"{s}: {c}" for s, c in srcs.items()])
                    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                 params={"chat_id": chat, "text": txt})
        time.sleep(3)

def daily_report():
    logs = fetch_logs()
    today_logs = [l for l in logs if l[2].startswith(str(date.today()))]
    total = len(today_logs)
    sources = {}
    for s, _, _ in today_logs:
        sources[s] = sources.get(s, 0) + 1
    summary = summarize_logs()
    body = f"📊 Logs Today: {total}\n" + "\n".join([f"{k}: {v}" for k, v in sources.items()]) + f"\n\n🧠 Summary:\n{summary}"
    send_email("🗞️ Daily Report", body)

schedule.every().day.at("07:00").do(daily_report)

@app.before_request
def check_token():
    if request.path.startswith("/api/") and API_TOKEN:
        if request.headers.get("X-API-TOKEN") != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 403

@app.route("/")
def home():
    logs = fetch_logs()[-30:]
    return render_template_string('''
        <h2>📘 Musa Log Suite</h2>
        <form method="post" action="/log"><input name="message" placeholder="Enter log"><input type="submit"></form>
        <ul>{% for s,m,t in logs %}<li><strong>[{{s}}]</strong> {{t}} – {{m}}</li>{% endfor %}</ul>
    ''', logs=logs)

@app.route("/log", methods=["POST"])
def log():
    msg = request.form.get("message")
    save_log("DASHBOARD", msg)
    return redirect("/")

@app.route("/api/v1/logs")
def api_logs():
    logs = fetch_logs()
    return jsonify([{"source": s, "message": m, "timestamp": t} for s, m, t in logs])

@app.route("/api/v1/search")
def api_search():
    q = request.args.get("q", "").lower()
    results = [l for l in fetch_logs() if q in l[1].lower()]
    return jsonify([{"source": s, "message": m, "timestamp": t} for s, m, t in results])

@app.route("/api/v1/stats")
def api_stats():
    logs = fetch_logs()
    total = len(logs)
    srcs = {}
    for s, _, _ in logs:
        srcs[s] = srcs.get(s, 0) + 1
    return jsonify({"total": total, "by_source": srcs})

@app.route("/api/v1/summary")
def api_summary():
    return jsonify({"summary": summarize_logs()})

def run_all():
    init_db()
    Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    Thread(target=telegram_bot).start()
    Thread(target=lambda: [schedule.run_pending() or time.sleep(60)]).start()

if __name__ == "__main__":
    run_all()
