import os
import time
import requests
import subprocess
from datetime import datetime
from flask import Flask, request, redirect, session, send_file, render_template_string
from threading import Thread
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ✅ Ensure logs.txt exists
if not os.path.exists("logs.txt"):
    open("logs.txt", "w").close()

# 🔐 Load secrets
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 8080))

# 🚀 Flask setup
app = Flask(__name__)
app.secret_key = "your_secret_key"  # 🔒 Replace with a secure secret in production

# 🔐 Session guard
def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# 🔑 Login route
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

# 📥 Download route (fixed)
@app.route("/download")
@login_required
def download():
    try:
        log_path = os.path.join(BASE_DIR, "logs.txt")
        return send_file(log_path, as_attachment=True)
    except Exception as e:
        return f"Download failed: {e}", 500
#Dashboard form logging
@app.route("/submit", methods=["POST"])
@login_required
def submit():
    message = request.form.get("message", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[DASHBOARD] {timestamp} - {message}\n"
    with open("logs.txt", "a") as f:
        f.write(entry)
    return redirect("/")

# 📬 Telegram log endpoint
@app.route("/log", methods=["POST"])
def log():
    message = request.form.get("message", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[TELEGRAM] {timestamp} - {message}\n"
    with open("logs.txt", "a") as f:
        f.write(entry)
    return "Log added"

# 🔍 Status ping
@app.route("/status")
def status():
    return "Bot is running"

# 📊 Dashboard home
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

# 🚪 Logout route
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/login")

# 🧵 Run Flask in thread
def start_flask():
    app.run(host="0.0.0.0", port=PORT)

Thread(target=start_flask).start()

# 🤖 Telegram bot listener
def telegram_listener():
    last_update_id = None
    while True:
        try:
            updates = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json().get("result", [])
            for update in updates:
                update_id = update["update_id"]
                if last_update_id is None or update_id > last_update_id:
                    last_update_id = update_id
                    msg = update.get("message", {}).get("text", "")
                    if msg.startswith("/log"):
                        log_msg = msg[4:].strip()
                        requests.post(f"http://localhost:{PORT}/log", data={"message": log_msg})
        except Exception as e:
            print(f"Error in Telegram listener: {e}")
        time.sleep(2)

Thread(target=telegram_listener).start() 
