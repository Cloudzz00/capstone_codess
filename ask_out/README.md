# Movie Date 🍿 – a "Will you watch a movie with me?" website (Flask)

A small Python/Flask site:

1. **Question page.** "Hey baby… Will you watch a movie with me?" The **No**
   button stays on screen but can't be pressed: it just shakes and pleads, and **Yes** grows
   with every try.
2. **Yes page.** Confetti, then a short form: what kind of movie, how to watch
   together (video call, Discord, watch party), the day, the time, and a note.
3. **"It's a movie date!" page.** A movie ticket showing the plan.
4. **Responses page.** Only you can see it, at `/responses?key=YOUR_KEY`. It
   shows everything she picked (saved in `responses.json`).

## Personalise it (optional)

The defaults already say "baby". To change anything, edit the top of `app.py`
(or set the values in the PythonAnywhere WSGI file, see step 7 below):

```python
THEIR_NAME = "baby"          # what you call her
YOUR_NAME = "your baby"      # how you sign off
RESPONSES_KEY = "change-me"  # password for /responses
MOVIE_GENRES = [...]         # the movie choices
PLACES = [...]               # how to watch together
```

## Run it on your own computer (optional)

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

---

# Step-by-step: deploy on Render (free alternative)

Use this if PythonAnywhere doesn't work for you. Your site will be at
`https://SOME-NAME.onrender.com`.

**Two things to know about Render's free plan:**
- The site **goes to sleep after 15 minutes** with no visitors. The next
  visit takes up to about a minute to load. **Open the link yourself a minute
  before you send it to her**, so it's awake.
- **Saved answers can disappear** when it sleeps or restarts (the
  `/responses` page starts empty again). Her answer still shows on her
  ticket page, so ask her to send you a screenshot 📸, or check
  `/responses` soon after she answers.

### Step 1 – Sign up
Go to <https://render.com>, click **Get Started**, and sign up with
**GitHub** (easiest, since your code is there).

### Step 2 – Create a web service
1. In the Render dashboard, click **+ New** → **Web Service**.
2. Choose **Git Provider → GitHub**, allow Render to see your repos, and
   pick **capstone_codess**.
   (Or paste the public URL `https://github.com/Cloudzz00/capstone_codess`
   under **Public Git Repository**.)

### Step 3 – Fill in the settings

| Setting            | Value                              |
|--------------------|------------------------------------|
| **Name**           | anything, e.g. `movie-date` (becomes the web address) |
| **Branch**         | `main`                             |
| **Root Directory** | `ask_out`                          |
| **Runtime / Language** | `Python 3`                     |
| **Build Command**  | `pip install -r requirements.txt`  |
| **Start Command**  | `gunicorn app:app`                 |
| **Instance Type**  | **Free**                           |

### Step 4 – Add your settings (environment variables)
Scroll to **Environment Variables** and add:

| Key             | Value                |
|-----------------|----------------------|
| `THEIR_NAME`    | `baby`               |
| `YOUR_NAME`     | `your baby`          |
| `RESPONSES_KEY` | `pick-a-secret-word` |

### Step 5 – Deploy
Click **Deploy Web Service**. Wait for the log to say **Your service is
live 🎉** (a few minutes the first time).

### Step 6 – Test and send
Click the `https://….onrender.com` link at the top of the page, try it
yourself, then send her the link 💜

**Updating later:** any change merged into `main` on GitHub redeploys
automatically. To redeploy by hand: **Manual Deploy → Deploy latest commit**.

**If it fails:** open the **Logs** tab. Most often the Root Directory isn't
`ask_out`, or the Start Command is mistyped.

---

# Step-by-step: deploy on PythonAnywhere (free)

Your site will end up at `https://YOUR_USERNAME.pythonanywhere.com`.
Everywhere below, replace `YOUR_USERNAME` with your PythonAnywhere username.

### Step 1 – Create a free account

1. Go to <https://www.pythonanywhere.com> and click **Pricing & signup**.
2. Click **Create a Beginner account** (free).
3. Choose your username carefully: it becomes the web address
   (e.g. username `moviedate` → `moviedate.pythonanywhere.com`).
4. Confirm your email and log in.

### Step 2 – Open a Bash console

1. On the Dashboard, click the **Consoles** tab at the top.
2. Under "Start a new console", click **Bash**.
   A black terminal window opens.

### Step 3 – Download the code

Paste this into the Bash console and press Enter:

```bash
git clone -b claude/ecstatic-cannon-4day69 https://github.com/Cloudzz00/capstone_codess.git
```

(If this code has been merged into `main`, you can leave out
`-b claude/ecstatic-cannon-4day69`.)

Check it worked:

```bash
ls ~/capstone_codess/ask_out
```

You should see `app.py  README.md  requirements.txt  static  templates`.

### Step 4 – Make sure Flask is installed

Flask is normally preinstalled. Check with:

```bash
python3.13 -c "import flask; print(flask.__version__)"
```

If it prints a version number, move on. If it shows an error, install it:

```bash
pip3.13 install --user Flask
```

(If your account doesn't have Python 3.13, use the newest version it has,
e.g. `python3.12` / `pip3.12`, and pick the same version in Step 5.)

### Step 5 – Create the web app

1. Click the **Web** tab at the top (in the ☰ menu on a phone).
2. Click **Add a new web app**.
3. It shows your free address (`YOUR_USERNAME.pythonanywhere.com`).
   Click **Next**.
4. Choose **Manual configuration** (⚠️ *not* "Flask", which creates its own
   sample app).
5. Choose **Python 3.13** (the same version as Step 4) and click **Next**.
6. Click **Next** again. You're now on your web app's settings page.

### Step 6 – Tell it where the code is

On the Web tab, scroll to the **Code** section:

- Click the path next to **Source code**, enter the path below and click ✓:

  ```
  /home/YOUR_USERNAME/capstone_codess/ask_out
  ```

- Do the same for **Working directory** (same path).

### Step 7 – Edit the WSGI file

1. Still in the **Code** section, click the link next to
   **WSGI configuration file**
   (it looks like `/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py`).
2. An editor opens. **Select everything and delete it.**
3. Paste this in, replacing `YOUR_USERNAME` and the secret word:

   ```python
   import os
   import sys

   path = "/home/YOUR_USERNAME/capstone_codess/ask_out"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["THEIR_NAME"] = "baby"
   os.environ["YOUR_NAME"] = "your baby"
   os.environ["RESPONSES_KEY"] = "pick-a-secret-word"

   from app import app as application
   ```

4. Click **Save** (top right), then go back to the **Web** tab.

### Step 8 – Static files (makes the page load faster)

On the Web tab, scroll to **Static files** and click
**Enter URL** / **Enter path**:

| URL        | Directory                                            |
|------------|------------------------------------------------------|
| `/static/` | `/home/YOUR_USERNAME/capstone_codess/ask_out/static` |

### Step 9 – Reload and test

1. Scroll to the top of the Web tab and click the big green
   **Reload YOUR_USERNAME.pythonanywhere.com** button.
2. Open `https://YOUR_USERNAME.pythonanywhere.com` and try it yourself:
   hover over **No**, press **Yes**, fill in the form.
3. Check your answers page:
   `https://YOUR_USERNAME.pythonanywhere.com/responses?key=pick-a-secret-word`
4. Your own test answer shows there. To clear it before sending the link,
   run this in the Bash console:

   ```bash
   rm ~/capstone_codess/ask_out/responses.json
   ```

### Step 10 – Send her the link 💌

Send `https://YOUR_USERNAME.pythonanywhere.com`, then check the responses
page to see what movie she picked.

---

## Troubleshooting

- **"Something went wrong" / error page.** On the Web tab, open the
  **Error log** link (in the "Log files" section). The last lines show the
  Python error. Usually the path in Step 6/7 has a typo or `YOUR_USERNAME`
  wasn't replaced.
- **"Hello from Flask!" or a PythonAnywhere default page.** You picked
  "Flask" instead of "Manual configuration", or the WSGI file still has the
  old contents. Redo Step 7 and Reload.
- **Page has no colours/styling.** Check the Static files path in Step 8,
  then Reload.
- **Changed something but the site looks the same.** Always click
  **Reload** on the Web tab after any change.

## Updating the site later

```bash
cd ~/capstone_codess && git pull
```

Then click **Reload** on the Web tab.

## Keep it online

Free web apps switch off after about 3 months unless renewed. Log in, open
the **Web** tab and click **Run until 3 months from today**.
