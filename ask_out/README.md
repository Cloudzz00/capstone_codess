# Ask Out – a "Will you go out with me?" website (Flask)

A small Python/Flask site:

1. **Question page.** "Will you go out with me?" The **No** button runs away
   whenever someone tries to click or tap it, and **Yes** grows with every try.
2. **Yes page.** Confetti, then a short form: pick a date idea, a day, a time
   and an optional note.
3. **It's a date! page.** A little "ticket" showing the plan.
4. **Responses page.** Only you can see it, at `/responses?key=YOUR_KEY`. It
   lists every answer submitted (saved in `responses.json`).

## Personalise it

Open `app.py` and change the settings at the top:

```python
THEIR_NAME = "Crush"        # who you're asking
YOUR_NAME = "Me"            # who's asking
RESPONSES_KEY = "change-me" # password for /responses
DATE_IDEAS = [...]          # the date options on the form
```

You can also put the name in the link itself, e.g.
`https://yourname.pythonanywhere.com/?to=Alex`.

## Run it on your computer

```bash
cd ask_out
```

```bash
pip install -r requirements.txt
```

```bash
python app.py
```

Then open http://127.0.0.1:5000

## Deploy on PythonAnywhere (free account works)

1. **Get the code onto PythonAnywhere.** Open a **Bash console** (Dashboard →
   *Consoles* → *Bash*) and clone your repo:

   ```bash
   git clone https://github.com/cloudzz00/capstone_codess.git
   ```

   (If the repo is private, upload the `ask_out` folder through the **Files**
   tab instead.)

2. **Create the web app.** Go to the **Web** tab → *Add a new web app* →
   *Next* → **Manual configuration** (not "Flask") → choose **Python 3.13**
   (or the newest offered) → *Next*.

3. **Point it at the code.** On the Web tab, set **Source code** to:

   ```
   /home/YOUR_USERNAME/capstone_codess/ask_out
   ```

4. **Edit the WSGI file.** On the Web tab, click the link next to
   **WSGI configuration file**, delete everything in it, and paste this
   (replace `YOUR_USERNAME` and the names/key):

   ```python
   import os
   import sys

   path = "/home/YOUR_USERNAME/capstone_codess/ask_out"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["THEIR_NAME"] = "Alex"
   os.environ["YOUR_NAME"] = "Sam"
   os.environ["RESPONSES_KEY"] = "pick-a-secret-word"

   from app import app as application
   ```

   Click **Save**.

5. **Static files (optional, makes CSS/JS load faster).** On the Web tab under
   **Static files**, add:

   | URL       | Directory                                              |
   |-----------|--------------------------------------------------------|
   | `/static/` | `/home/YOUR_USERNAME/capstone_codess/ask_out/static`   |

6. Flask is already installed on PythonAnywhere. If it ever says it's missing,
   run this in a Bash console:

   ```bash
   pip3.13 install --user Flask
   ```

7. Press the green **Reload** button at the top of the Web tab and open
   `https://YOUR_USERNAME.pythonanywhere.com`.

To see the answers, visit
`https://YOUR_USERNAME.pythonanywhere.com/responses?key=pick-a-secret-word`.

**Updating later:** in a Bash console run
`cd ~/capstone_codess && git pull`, then press **Reload** on the Web tab.

**If something goes wrong:** the **Error log** link on the Web tab shows the
Python error.

> Free PythonAnywhere apps must be renewed from the Web tab every few months
> (there's a "Run until 3 months from today" button).
