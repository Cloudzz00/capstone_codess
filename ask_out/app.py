"""A small "Will you watch a movie with me?" website, built with Flask.

Edit the settings below (or set the matching environment variables), then
run locally with:  python app.py   and open http://127.0.0.1:5000
"""

import json
import os
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

# ---------------------------------------------------------------------------
# Settings: change these to personalise the page.
# ---------------------------------------------------------------------------
THEIR_NAME = os.environ.get("THEIR_NAME", "baby")       # what you call her
YOUR_NAME = os.environ.get("YOUR_NAME", "your baby")    # how you sign off
# Password for the page that lists answers: /responses?key=...
RESPONSES_KEY = os.environ.get("RESPONSES_KEY", "change-me")
# Optional: a Discord webhook URL. Each answer is posted to that channel.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# Kinds of movie she can pick from.
MOVIE_GENRES = [
    ("romcom", "Rom-com 💜"),
    ("horror", "Horror (I'll protect you) 👻"),
    ("action", "Action 💥"),
    ("comedy", "Comedy 😂"),
    ("animated", "Animated 🧸"),
    ("youpick", "You pick, baby!"),
]

# How to watch together from far away (we're long distance).
PLACES = [
    ("call", "Video call & press play together 📞"),
    ("discord", "Discord screen share 🎮"),
    ("party", "Watch party (Teleparty) 🍿"),
]
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
RESPONSES_FILE = BASE_DIR / "responses.json"
_lock = threading.Lock()

app = Flask(__name__)


def their_name():
    """Allow ?to=Name in the link to override the configured name."""
    name = request.args.get("to", "").strip()
    return name[:40] if name else THEIR_NAME


def load_responses():
    if not RESPONSES_FILE.exists():
        return []
    try:
        return json.loads(RESPONSES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_response(entry):
    try:
        with _lock:
            data = load_responses()
            data.append(entry)
            RESPONSES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Could not save to {RESPONSES_FILE}: {exc}", flush=True)


def format_answer(entry):
    lines = [
        "💜 **She said YES to the movie date!** 🎬",
        f"🎞️ Movie: {entry['genre']}",
        f"📞 How: {entry['place']}",
        f"📅 When: {entry['date']} at {entry['time']}",
    ]
    if entry["note"]:
        lines.append(f"📝 Note: {entry['note']}")
    lines.append(f"🕒 Answered: {entry['submitted_at']}")
    return "\n".join(lines)


def _post_to_discord(text):
    body = json.dumps({
        "content": text[:1900],
        "allowed_mentions": {"parse": []},  # never ping @everyone
    }).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "MovieDateInvite/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Sent answer to Discord (HTTP {resp.status})", flush=True)
    except Exception as exc:  # don't let a Discord problem break her page
        print(f"Could not send answer to Discord: {exc}", flush=True)


def notify(entry):
    """Make sure you see her answer even if the saved file gets wiped."""
    text = format_answer(entry)
    # Always shows up in the host's logs (Render: the Logs tab).
    print("NEW ANSWER >>> " + json.dumps(entry, ensure_ascii=False), flush=True)
    if DISCORD_WEBHOOK_URL:
        threading.Thread(target=_post_to_discord, args=(text,), daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html", name=their_name(), me=YOUR_NAME)


@app.route("/yes")
def yes():
    return render_template(
        "yes.html", name=their_name(), me=YOUR_NAME,
        genres=MOVIE_GENRES, places=PLACES,
    )


@app.route("/plan", methods=["POST"])
def plan():
    entry = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "name": request.form.get("name", "")[:40],
        "genre": dict(MOVIE_GENRES).get(request.form.get("genre"), "You pick, baby!"),
        "place": dict(PLACES).get(request.form.get("place"), PLACES[0][1]),
        "date": request.form.get("date", "")[:20],
        "time": request.form.get("time", "")[:10],
        "note": request.form.get("note", "").strip()[:500],
    }
    save_response(entry)
    notify(entry)
    return redirect(url_for("done", to=entry["name"] or None,
                            genre=entry["genre"], place=entry["place"],
                            date=entry["date"], time=entry["time"]))


@app.route("/done")
def done():
    return render_template(
        "done.html",
        name=their_name(),
        me=YOUR_NAME,
        genre=request.args.get("genre", ""),
        place=request.args.get("place", ""),
        date=request.args.get("date", ""),
        time=request.args.get("time", ""),
    )


@app.route("/responses")
def responses():
    if request.args.get("key") != RESPONSES_KEY:
        abort(404)
    return render_template("responses.html",
                           responses=list(reversed(load_responses())))


if __name__ == "__main__":
    app.run(debug=True)
