// Floating hearts in the background on every page.
(function hearts() {
  const box = document.querySelector(".hearts");
  if (!box) return;
  const icons = ["💜", "💜", "🍿", "🎬", "🔮", "🎞️"];
  function spawn() {
    const h = document.createElement("span");
    h.textContent = icons[Math.floor(Math.random() * icons.length)];
    h.style.left = Math.random() * 100 + "vw";
    h.style.fontSize = 14 + Math.random() * 22 + "px";
    h.style.animationDuration = 6 + Math.random() * 6 + "s";
    box.appendChild(h);
    setTimeout(() => h.remove(), 13000);
  }
  for (let i = 0; i < 6; i++) setTimeout(spawn, i * 400);
  setInterval(spawn, 900);
})();

// The question page: "No" can't be pressed and "Yes" keeps growing.
function initQuestion(name) {
  const noBtn = document.getElementById("noBtn");
  const yesBtn = document.getElementById("yesBtn");
  const hint = document.getElementById("hint");
  name = name || "baby";
  const lines = [
    `Are you sure, ${name}?`,
    "Really sure?? 🥺",
    "I'll buy the popcorn 🍿",
    `Pretty please, ${name}?`,
    "You can pick the movie!",
    "You're breaking my heart 💔",
    `Okay ${name}, now you HAVE to say yes`,
  ];
  let tries = 0;
  let yesSize = 1.1;

  // "No" stays put and stays visible, but it can't be pressed:
  // it just shakes, pleads, and makes "Yes" a little bigger.
  function refuse(e) {
    if (e) e.preventDefault();
    noBtn.classList.remove("shake");
    void noBtn.offsetWidth; // restart the shake animation
    noBtn.classList.add("shake");

    hint.textContent = lines[Math.min(tries, lines.length - 1)];
    tries++;
    yesSize = Math.min(yesSize + 0.2, 2.2);
    yesBtn.style.fontSize = yesSize + "rem";
  }

  noBtn.addEventListener("mouseenter", refuse);
  noBtn.addEventListener("click", refuse);
  noBtn.addEventListener("touchstart", refuse, { passive: false });
}

// Plan form: don't allow dates in the past, default to tomorrow.
function initPlanForm() {
  const input = document.getElementById("dateInput");
  if (!input) return;
  const iso = (d) => {
    const off = d.getTimezoneOffset() * 60000;
    return new Date(d - off).toISOString().slice(0, 10);
  };
  const today = new Date();
  const tomorrow = new Date(today.getTime() + 86400000);
  input.min = iso(today);
  input.value = iso(tomorrow);
}

function prettifyDate() {
  const el = document.getElementById("prettyDate");
  if (el && el.dataset.date) {
    const d = new Date(el.dataset.date + "T00:00:00");
    if (!isNaN(d)) {
      el.textContent = d.toLocaleDateString(undefined, {
        weekday: "long", month: "long", day: "numeric",
      });
    }
  }
  const t = document.getElementById("prettyTime");
  if (t && /^\d{2}:\d{2}$/.test(t.dataset.time || "")) {
    const [h, m] = t.dataset.time.split(":").map(Number);
    t.textContent = `${(h % 12) || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
  }
}

function confetti() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const colors = ["#7c3aed", "#a78bfa", "#c4b5fd", "#e9d5ff", "#ffd166"];
  for (let i = 0; i < 80; i++) {
    const c = document.createElement("div");
    c.className = "confetti";
    c.style.left = Math.random() * 100 + "vw";
    c.style.background = colors[i % colors.length];
    c.style.animationDuration = 2 + Math.random() * 2.5 + "s";
    c.style.animationDelay = Math.random() * 0.6 + "s";
    document.body.appendChild(c);
    setTimeout(() => c.remove(), 5500);
  }
}
