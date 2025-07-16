import os
import requests
import subprocess
import time
from datetime import datetime
from flask import Flask, request, redirect, session, send_file, render_template_string
from threading import Thread
from dotenv import load_dotenv

# ✅ Create logs.txt if it doesn't exist
if not os.path.exists("logs.txt"):
    open("logs.txt", "w").close()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 8080))

app = Flask(__name__)
app.secret_key = "your_secret_key"

# 🧠 Authentication
def login_required(f):
    def wrapper(*args, **kwargs):
        if "logged_in" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ✅ Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "pass123":
            session["logged_in"] = True
            return redirect("/")
        return "Invalid credentials"
    return '''
    <form method="post">
        <input name="username" placeholder="Username"><br>
        <input name="password" placeholder="Password" type="password"><br>
        <input type="submit" value="Login">
    </form>
    '''

# 📥 Download logs.txt safely
@app.route("/download")
@login_required
def download():
    log_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "logs.txt")
    return send_file(log_path, as_attachment=True)

# 📬 Telegram Log Entry
@app.route("/log", methods=["POST"])
def log():
    msg = request.form.get("message", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[TELEGRAM] {timestamp} - {msg}\n"
    with open("logs.txt", "a") as f:
        f.write(entry)
    return "Log added"

# 📝 Dashboard Form Submit
@app.route("/submit", methods=["POST"])
@login_required
def submit():
    msg = request.form.get("message", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[DASHBOARD] {timestamp} - {msg}\n"
    with open("logs.txt", "a") as f:
        f.write(entry)
    return redirect("/")

# 🔍 Status Route
@app.route("/status")
def status():
    return "Bot is running"

# 📊 Dashboard Display
@app.route("/")
@login_required
def dashboard():
    try:
        with open("logs.txt", "r") as f:
            logs = f.readlines()
    except:
        logs = []
    return render_template_string('''
    <h2>🧠 Log Dashboard</h2>
    <form method="post" action="/submit">
        <input name="message" placeholder="Add log">
        <input type="submit" value="Submit">
    </form>
    <a href="/download">📥 Download Logs</a>
    <ul>
    {% for log in logs %}
        <li>{{ log }}</li>
    {% endfor %}
    </ul>
    ''', logs=logs)

# 🚪 Logout
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/login")

# 🧵 Run background thread
def start_flask():
    app.run(host="0.0.0.0", port=PORT)

Thread(target=start_flask).start()

# 🤖 Telegram Bot Listener
def telegram_listener():
    last_update = None
    while True:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        res = requests.get(url).json()
        updates = res.get("result", [])
        if updates:
            for update in updates:
                update_id = update["update_id"]
                if last_update is None or update_id > last_update:
                    last_update = update_id
                    msg = update.get("message", {}).get("text", "")
                    if msg.startswith("/log"):
                        content = msg[4:].strip()
                        data = {"message": content}
                        requests.post("http://localhost:{}/log".format(PORT), data=data)
        time.sleep(2)

Thread(target=telegram_listener).start()
