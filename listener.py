import os, requests, subprocess, time
from datetime import datetime
from flask import Flask, request, redirect, session, send_file, render_template_string
from threading import Thread
from dotenv import load_dotenv
if not os.path.exists("logs.txt"):
    open("logs.txt", "w").close()

# 🔐 Load environment variables
load_dotenv()
token = os.getenv("TOKEN")
chat_id = os.getenv("CHAT_ID")
base_url = f"https://api.telegram.org/bot{token}"

# 📓 Logging
log_file = "logs.txt"
today = datetime.now().strftime("%Y-%m-%d")

# 🚀 Flask config
app = Flask(__name__)
app.secret_key = "supersecretkey"

USERS = {
    "admin": {"password": "pass123"},
    "viewer": {"password": "view123"}
}

# 📬 Send message to Telegram
def send_message(text):
    try:
        requests.post(f"{base_url}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })
    except:
        with open(log_file, "a") as f:
            f.write(f"{today} ⚠️ Telegram failed\n")

# 💬 Handle commands from Telegram
def handle_command(cmd):
    if cmd.startswith("/log "):
        msg = cmd[5:]
        with open(log_file, "a") as f:
            f.write(f"{today} {msg}\n")
        send_message(f"✅ Logged:\n`{today} {msg}`")
    elif cmd == "/status":
        up = subprocess.getoutput("uptime")
        mem = subprocess.getoutput("free -h")
        send_message(f"*🧠 Uptime:* `{up}`\n```\n{mem}\n```")
    elif cmd == "/report":
        with open(log_file) as f:
            lines = [l for l in f if today in l]
        send_message("*📦 Report:*\n" + "".join(lines[-50:]) if lines else "🧹 Nothing yet.")
    elif cmd == "/loglist":
        with open(log_file) as f:
            lines = f.readlines()
        send_message("*📜 Recent Logs:*\n" + "".join(lines[-20:]) if lines else "🧹 Empty.")
    else:
        send_message("❓ Unknown command")

# 🔄 Telegram polling loop
def telegram_loop():
    offset = None
    while True:
        try:
            params = {"timeout": 5}
            if offset:
                params["offset"] = offset
            updates = requests.get(f"{base_url}/getUpdates", params=params).json()
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                if str(msg.get("chat", {}).get("id")) == chat_id and "text" in msg:
                    handle_command(msg["text"].strip())
        except:
            time.sleep(2)

# 🧠 Background health monitor
def health_monitor():
    while True:
        cpu = subprocess.getoutput("top -bn1 | grep 'Cpu(s)'")
        disk = subprocess.getoutput("df -h / | tail -1")
        if "90.0%" in cpu:
            send_message("🚨 CPU usage high!")
        if "10%" in disk:
            send_message("📉 Disk space critically low!")
        time.sleep(60)

# 🔐 Login protection
def login_required(view):
    def wrapped(*args, **kwargs):
        if session.get("user"):
            return view(*args, **kwargs)
        return redirect("/login")
    wrapped.__name__ = view.__name__
    return wrapped

# 🔑 Login screen
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u in USERS and USERS[u]["password"] == p:
            session["user"] = u
            return redirect("/")
        return "<h3>❌ Incorrect login. <a href='/login'>Try again</a></h3>"
    return """<form method='post'>
    <h3>🔐 Login</h3>
    <input name='username'><br>
    <input name='password' type='password'><br>
    <button>Login</button></form>"""

# 🚪 Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# 📊 Dashboard page
@app.route("/")
@login_required
def dashboard():
    if not os.path.exists(log_file):
        open(log_file, "w").close()
    with open(log_file) as f:
        lines = f.readlines()
    telegram_logs = [l for l in lines if "[Web]" not in l]
    web_logs = [l for l in lines if "[Web]" in l]

    return render_template_string("""
    <html><head><title>Bot Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script></head><body>
    <h2>📘 Listener Dashboard</h2>

    <div id="chart" style="width:600px;height:300px;"></div>
    <script>
    Plotly.newPlot('chart', [{
      x: ['Telegram', 'Dashboard'],
      y: [{{tg}}, {{web}}],
      type: 'bar'
    }]);
    </script>

    <form method='post' action='/log'>
        <input name='message' placeholder='Log message'><button>➕ Log</button>
    </form>
    <p><a href='/download'>📥 Download Logs</a> | <a href='/logout'>Logout</a></p>
    <pre>{{logs}}</pre></body></html>
    """, logs="".join(lines[-20:]), tg=len(telegram_logs), web=len(web_logs))

# ➕ Add dashboard log
@app.route("/log", methods=["POST"])
@login_required
def add_log():
    msg = request.form.get("message")
    if msg:
        with open(log_file, "a") as f:
            f.write(f"{today} [Web] {msg}\n")
    return redirect("/")

# 📥 Download logs
@app.route("/download")
@login_required
def download():
    log_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "logs.txt")
    return send_file(log_path, as_attachment=True)
# 🚀 Start all services
def start_services():
    Thread(target=telegram_loop).start()
    Thread(target=health_monitor).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_services()
