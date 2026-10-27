// Shared helpers: screens, talking to the server, saving on the phone, read aloud, share.

// Where the server lives. "" means "the same server that serves this page".
const API_URL = "";

const $ = (id) => document.getElementById(id);

// ---------- Screens ----------
const screenHooks = {}; // screen name -> function to run when it opens

function show(id) {
  document.querySelectorAll(".screen").forEach((s) => { s.hidden = s.id !== id; });
  window.scrollTo(0, 0);
  if (screenHooks[id]) screenHooks[id]();
  const heading = document.querySelector(`#${id} h1`);
  if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); } // screen readers announce the new screen
}

document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) show(go.dataset.go);
  const pick = e.target.closest("[data-pick]");
  if (pick) { const input = $(pick.dataset.pick); input.value = ""; input.click(); }
});

// ---------- The shared "working" screen ----------
let jobId = 0; // lets Cancel ignore a job that's still running

function startJob({ title, steps, note = true }) {
  const id = ++jobId;
  $("working-title").textContent = title;
  $("working-sub").textContent = "This takes a few seconds.";
  $("working-note").hidden = !note;
  const list = $("working-steps");
  list.innerHTML = "";
  steps.forEach((words, i) => {
    const li = document.createElement("li");
    li.id = `step-${i}`;
    const box = document.createElement("span");
    box.className = "step-box";
    const label = document.createElement("span");
    label.textContent = words;
    li.append(box, label);
    list.append(li);
  });
  show("working");
  return {
    isCurrent: () => id === jobId,
    step(i, state) {
      const li = $(`step-${i}`);
      if (!li) return;
      li.classList.remove("active", "done");
      if (state) li.classList.add(state);
    },
    say(words) { if (id === jobId) $("working-sub").textContent = words; },
  };
}

$("cancel-work").addEventListener("click", () => { jobId++; show("home"); });

// ---------- Errors ----------
let retryAction = null;

function showError(message, { title = "Something went wrong", retry = null } = {}) {
  $("error-title").textContent = title;
  $("error-text").textContent = message;
  retryAction = retry;
  $("error-retry").hidden = !retry;
  show("error");
}
$("error-retry").addEventListener("click", () => retryAction && retryAction());

// ---------- Talking to the server ----------
async function api(path, body, { method = body ? "POST" : "GET", timeoutMs = 25000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    throw new Error(
      err.name === "AbortError"
        ? "The server is taking too long. If the app was asleep, it can take up to a minute to wake up. Please try again."
        : "We couldn't reach the server. Check your internet and try again."
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch (_) {}
    throw new Error(typeof detail === "string" && detail ? detail : "The server had a problem. Please try again.");
  }
  return res.json();
}

// ---------- Saving on this phone only ----------
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch (_) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* storage blocked */ }
  },
};

// ---------- Read aloud ----------
const speechText = {}; // screen name -> words to read

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-speak]");
  if (!btn) return;
  const words = speechText[btn.dataset.speak];
  if (!words || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(words);
  speech.rate = 0.9;
  speech.lang = "en-US";
  window.speechSynthesis.speak(speech);
});

// ---------- Share (the phone's share menu, or copy) ----------
async function shareText(text) {
  try {
    if (navigator.share) {
      await navigator.share({ title: "CareCircle", text });
    } else {
      await navigator.clipboard.writeText(text);
      alert("Copied. You can paste it into a message.");
    }
  } catch (_) { /* closed the share menu */ }
}

// ---------- Small helpers ----------
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // textContent keeps outside text safe
  return node;
}

function titleCase(s) {
  return s.replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

// Install as an app and open offline.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("service-worker.js").catch(() => {});
}
