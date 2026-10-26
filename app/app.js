// CareCircle web app.
// Flow: Home -> Camera (or Paste) -> Checking -> Result.
// Photos are read on the phone with Tesseract.js. Only the words are sent to the server.

// Where the Scam Check API lives. "" means "the same server that serves this page".
const API_URL = "";

// ---------- Screens ----------
function show(id) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.hidden = s.id !== id;
  });
  window.scrollTo(0, 0);
}

// Any button with data-go="screenName" switches screens.
document.querySelectorAll("[data-go]").forEach((btn) => {
  btn.addEventListener("click", () => show(btn.dataset.go));
});

// ---------- Camera ----------
const photoInput = document.getElementById("photo-input");
const photoPreview = document.getElementById("photo-preview");
const checkPhotoBtn = document.getElementById("check-photo");
let chosenPhoto = null;

document.getElementById("shutter").addEventListener("click", () => photoInput.click());

photoInput.addEventListener("change", () => {
  chosenPhoto = photoInput.files[0] || null;
  if (!chosenPhoto) return;
  photoPreview.src = URL.createObjectURL(chosenPhoto);
  photoPreview.hidden = false;
  document.getElementById("viewfinder-hint").hidden = true;
  document.getElementById("shutter-label").textContent = "Take another";
  checkPhotoBtn.hidden = false;
});

checkPhotoBtn.addEventListener("click", () => {
  if (chosenPhoto) checkPhoto(chosenPhoto);
});

// ---------- Paste ----------
document.getElementById("check-paste").addEventListener("click", () => {
  const text = document.getElementById("paste-text").value.trim();
  if (text) checkText(text, { fromPhoto: false });
});

// ---------- Checking ----------
let runId = 0; // lets "Cancel" ignore a check that is still running

document.getElementById("cancel-check").addEventListener("click", () => {
  runId++;
  show("home");
});

function setStep(id, state) {
  const li = document.getElementById(id);
  li.classList.remove("active", "done");
  if (state) li.classList.add(state);
}

async function checkPhoto(file) {
  const myRun = ++runId;
  show("checking");
  setStep("step-read", "active");
  setStep("step-check", null);

  try {
    if (!window.Tesseract) throw new Error("The text reader didn't load. Check your internet and try again.");
    const { data } = await Tesseract.recognize(file, "eng");
    if (myRun !== runId) return;
    const text = (data.text || "").trim();
    if (text.length < 5) {
      throw new Error("We couldn't find any words. Try again with more light, and hold the phone closer.");
    }
    await checkText(text, { fromPhoto: true, run: myRun });
  } catch (err) {
    if (myRun === runId) showError(err.message);
  }
}

async function checkText(text, { fromPhoto, run } = {}) {
  const myRun = run ?? ++runId;
  show("checking");
  setStep("step-read", "done");
  setStep("step-check", "active");
  document.getElementById("checking-sub").textContent = fromPhoto
    ? "We found the words. Now checking them."
    : "This takes a few seconds.";

  try {
    const res = await fetch(`${API_URL}/check-message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 5000) }),
    });
    if (!res.ok) throw new Error("The checker didn't answer. Please try again.");
    const result = await res.json();
    if (myRun !== runId) return;
    setStep("step-check", "done");
    showResult(result, text);
  } catch (err) {
    if (myRun === runId) {
      showError(err.message === "Failed to fetch" ? "We couldn't reach the checker. Check your internet and try again." : err.message);
    }
  }
}

// ---------- Result ----------
const VERDICT_STYLE = {
  scam: {
    color: "bg-scam",
    reasonsHeading: "Why we think so",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><path d="M8 2.5h8l5.5 5.5v8L16 21.5H8L2.5 16V8z" fill="#fff" stroke="#1F1F1F" stroke-width="1.6"/><path d="M9 9l6 6M15 9l-6 6" stroke="#1F1F1F" stroke-width="2.2" stroke-linecap="round"/></svg>',
  },
  careful: {
    color: "bg-careful",
    reasonsHeading: "Why to be careful",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><path d="M12 2.5L22 20.5H2z" fill="#fff" stroke="#1F1F1F" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 9v5" stroke="#1F1F1F" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.2" r="1.3" fill="#1F1F1F"/></svg>',
  },
  safe: {
    color: "bg-safe",
    reasonsHeading: "Why it looks safe",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#fff" stroke="#1F1F1F" stroke-width="1.6"/><path d="M7 12.5l3.3 3.3L17 9" fill="none" stroke="#1F1F1F" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  },
};

let lastResult = null;

function showResult(result, text) {
  const style = VERDICT_STYLE[result.verdict] || VERDICT_STYLE.careful;
  lastResult = result;

  const verdict = document.getElementById("verdict");
  verdict.className = `card card--shadow verdict ${style.color}`;
  document.getElementById("verdict-icon").innerHTML = style.icon; // our own fixed SVG, not user text
  document.getElementById("verdict-title").textContent = result.title;

  const n = result.warning_signs;
  const signs = n === 0 ? "no warning signs" : `${n} warning sign${n === 1 ? "" : "s"}`;
  document.getElementById("verdict-tag").innerHTML = "";
  const strong = document.createElement("strong");
  strong.textContent = result.confidence;
  document.getElementById("verdict-tag").append(strong, ` · ${signs}`);

  // textContent (never innerHTML) for anything that came from the message.
  document.getElementById("shown-text").textContent = text;

  document.getElementById("reasons-heading").textContent = style.reasonsHeading;
  const reasons = result.reasons.length
    ? result.reasons
    : ["We didn't find any of the usual warning signs."];
  const list = document.getElementById("reasons");
  list.innerHTML = "";
  reasons.forEach((reason, i) => {
    const card = document.createElement("div");
    card.className = "card reason";
    const num = document.createElement("span");
    num.className = `reason-num ${result.verdict === "safe" ? "bg-safe" : style.color}`;
    num.textContent = result.verdict === "safe" ? "✓" : String(i + 1);
    const words = document.createElement("span");
    words.textContent = reason;
    card.append(num, words);
    list.append(card);
  });

  document.getElementById("advice").textContent = result.advice;
  saveLastCheck(result, text);
  show("result");
}

function showError(message) {
  document.getElementById("error-text").textContent = message;
  show("error");
}

// ---------- Read aloud ----------
document.getElementById("read-aloud").addEventListener("click", () => {
  if (!lastResult || !("speechSynthesis" in window)) return;
  const words = [
    lastResult.title + ".",
    ...lastResult.reasons,
    "What to do: " + lastResult.advice,
  ].join(" ");
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(words);
  speech.rate = 0.9; // a little slower than normal
  window.speechSynthesis.speak(speech);
});

// ---------- Tell family (uses the phone's share menu) ----------
document.getElementById("tell-family").addEventListener("click", async () => {
  if (!lastResult) return;
  const text = `CareCircle checked a message for me: "${lastResult.title}". ${lastResult.reasons.join(" ")}`;
  try {
    if (navigator.share) {
      await navigator.share({ title: "CareCircle", text });
    } else {
      await navigator.clipboard.writeText(text);
      alert("Copied. You can paste it into a message to your family.");
    }
  } catch (_) {
    // The person closed the share menu. Nothing to do.
  }
});

// ---------- Last check on the home screen (saved only on this phone) ----------
const TAG_LABEL = { scam: "Scam", careful: "Careful", safe: "Safe" };

function saveLastCheck(result, text) {
  try {
    const snippet = text.length > 40 ? text.slice(0, 40) + "…" : text;
    localStorage.setItem("lastCheck", JSON.stringify({ verdict: result.verdict, snippet }));
  } catch (_) { /* storage blocked: skip */ }
  renderLastCheck();
}

function renderLastCheck() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("lastCheck")); } catch (_) {}
  const box = document.getElementById("last-check");
  if (!saved) { box.hidden = true; return; }
  document.getElementById("last-check-text").textContent = saved.snippet;
  const tag = document.getElementById("last-check-tag");
  tag.textContent = TAG_LABEL[saved.verdict] || "Checked";
  tag.className = `tag bg-${saved.verdict}`;
  box.hidden = false;
}
renderLastCheck();

// ---------- Install as an app (works offline for the screens) ----------
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("service-worker.js").catch(() => {});
}
