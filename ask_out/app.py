"""A small "Will you go out with me?" website, built with Flask.

Edit the settings below (or set the matching environment variables), then
run locally with:  python app.py   and open http://127.0.0.1:5000
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

# ---------------------------------------------------------------------------
# Settings: change these to personalise the page.
# ---------------------------------------------------------------------------
THEIR_NAME = os.environ.get("THEIR_NAME", "Crush")      # who you're asking
YOUR_NAME = os.environ.get("YOUR_NAME", "Me")           # who's asking
# Password for the page that lists answers: /responses?key=...
RESPONSES_KEY = os.environ.get("RESPONSES_KEY", "change-me")

DATE_IDEAS = [
    ("coffee", "Coffee & a long walk"),
    ("dinner", "Dinner somewhere cosy"),
    ("movie", "A movie night"),
    ("picnic", "A picnic in the park"),
    ("arcade", "Arcade games & ice cream"),
    ("surprise", "Surprise me!"),
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
    with _lock:
        data = load_responses()
        data.append(entry)
        RESPONSES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.route("/")
def index():
    return render_template("index.html", name=their_name(), me=YOUR_NAME)


@app.route("/yes")
def yes():
    return render_template(
        "yes.html", name=their_name(), me=YOUR_NAME, ideas=DATE_IDEAS
    )


@app.route("/plan", methods=["POST"])
def plan():
    ideas = dict(DATE_IDEAS)
    idea_key = request.form.get("idea", "")
    entry = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "name": request.form.get("name", "")[:40],
        "idea": ideas.get(idea_key, "Surprise me!"),
        "date": request.form.get("date", "")[:20],
        "time": request.form.get("time", "")[:10],
        "note": request.form.get("note", "").strip()[:500],
    }
    save_response(entry)
    return redirect(url_for("done", to=entry["name"] or None,
                            idea=entry["idea"], date=entry["date"],
                            time=entry["time"]))


@app.route("/done")
def done():
    return render_template(
        "done.html",
        name=their_name(),
        me=YOUR_NAME,
        idea=request.args.get("idea", ""),
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
