// Check a message for scams: from a photo/screenshot, or pasted text.

screenHooks.scan = () => OCR.warmUp();

["scan-camera", "scan-gallery"].forEach((id) => {
  $(id).addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) checkPhoto(file);
  });
});

$("check-paste").addEventListener("click", () => {
  const text = $("paste-text").value.trim();
  $("paste-error").hidden = text.length > 0;
  if (text) checkMessage(text, { fromPhoto: false });
});

async function checkPhoto(file) {
  const job = startJob({ title: "Checking it for you…", steps: ["Reading the words", "Looking for warning signs"] });
  job.step(0, "active");
  try {
    const { text, confidence } = await OCR.read(file, {
      onProgress: (words, progress) => job.say(progress == null ? words : `${words} ${Math.round(progress * 100)}%`),
    });
    if (!job.isCurrent()) return;
    if (text.replace(/[^A-Za-z]/g, "").length < 8) {
      showError(
        "Try again with the words filling more of the photo, in good light. A screenshot of the message works best.",
        { title: "We couldn't find the words", retry: () => show("scan") }
      );
      return;
    }
    job.step(0, "done");
    await checkMessage(text, { fromPhoto: true, job, lowConfidence: confidence < 60 });
  } catch (err) {
    if (job.isCurrent()) showError(err.message, { retry: () => show("scan") });
  }
}

async function checkMessage(text, { fromPhoto, job, lowConfidence = false }) {
  job = job || startJob({ title: "Checking it for you…", steps: ["Reading the words", "Looking for warning signs"], note: false });
  job.step(0, "done");
  job.step(1, "active");
  job.say("Looking for warning signs…");
  try {
    const result = await api("/check-message", { text: text.slice(0, 5000) });
    if (!job.isCurrent()) return;
    showScamResult(result, text, { fromPhoto, lowConfidence });
  } catch (err) {
    if (job.isCurrent()) showError(err.message, { retry: () => checkMessage(text, { fromPhoto }) });
  }
}

const VERDICT_STYLE = {
  scam: {
    color: "bg-scam", tag: "Scam", reasonsHeading: "Why we think so",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><path d="M8 2.5h8l5.5 5.5v8L16 21.5H8L2.5 16V8z" fill="#fff" stroke="#1F1F1F" stroke-width="1.6"/><path d="M9 9l6 6M15 9l-6 6" stroke="#1F1F1F" stroke-width="2.2" stroke-linecap="round"/></svg>',
  },
  careful: {
    color: "bg-careful", tag: "Careful", reasonsHeading: "Why to be careful",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><path d="M12 2.5L22 20.5H2z" fill="#fff" stroke="#1F1F1F" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 9v5" stroke="#1F1F1F" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.2" r="1.3" fill="#1F1F1F"/></svg>',
  },
  safe: {
    color: "bg-safe", tag: "Safe", reasonsHeading: "Why it looks safe",
    icon: '<svg class="solid" width="56" height="56" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#fff" stroke="#1F1F1F" stroke-width="1.6"/><path d="M7 12.5l3.3 3.3L17 9" fill="none" stroke="#1F1F1F" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  },
};

let lastScam = null;

function showScamResult(result, text, { fromPhoto, lowConfidence }) {
  const style = VERDICT_STYLE[result.verdict] || VERDICT_STYLE.careful;
  lastScam = { result, text };

  $("verdict").className = `card card--shadow verdict ${style.color}`;
  $("verdict-icon").innerHTML = style.icon; // our own fixed drawing, never outside text
  $("verdict-title").textContent = result.title;

  const n = result.warning_signs;
  const signs = n === 0 ? "no warning signs" : `${n} warning sign${n === 1 ? "" : "s"}`;
  const tag = $("verdict-tag");
  tag.textContent = "";
  tag.append(el("strong", "", result.confidence), ` · ${signs}`);

  $("shown-text").textContent = text;
  $("fix-words").hidden = !fromPhoto;
  $("fix-words").textContent = lowConfidence
    ? "Parts of the photo were hard to read. Fix the words and check again"
    : "Words look wrong? Fix them and check again";

  $("reasons-heading").textContent = style.reasonsHeading;
  const reasons = result.reasons.length ? result.reasons : ["We didn't find any of the usual warning signs."];
  const list = $("reasons");
  list.innerHTML = "";
  reasons.forEach((reason, i) => {
    const card = el("div", "card reason");
    card.append(el("span", `reason-num ${style.color}`, result.verdict === "safe" ? "✓" : String(i + 1)), el("span", "", reason));
    list.append(card);
  });

  $("advice").textContent = result.advice;
  speechText.result = [result.title + ".", `${result.confidence}.`, ...result.reasons, "What to do: " + result.advice].join(" ");

  store.set("lastCheck", { verdict: result.verdict, snippet: text.length > 40 ? text.slice(0, 40) + "…" : text });
  renderLastCheck();
  show("result");
}

$("fix-words").addEventListener("click", () => {
  if (!lastScam) return;
  $("paste-text").value = lastScam.text;
  show("paste");
});

$("share-result").addEventListener("click", () => {
  if (!lastScam) return;
  const { result } = lastScam;
  shareText(`CareCircle checked a message for me: "${result.title}" (${result.confidence}). ${result.reasons.join(" ")}`);
});

function renderLastCheck() {
  const saved = store.get("lastCheck", null);
  const box = $("last-check");
  if (!saved || !VERDICT_STYLE[saved.verdict]) { box.hidden = true; return; }
  $("last-check-text").textContent = saved.snippet;
  const tag = $("last-check-tag");
  tag.textContent = VERDICT_STYLE[saved.verdict].tag;
  tag.className = `tag ${VERDICT_STYLE[saved.verdict].color}`;
  box.hidden = false;
}
renderLastCheck();
