// Pill Check: read a pill bottle label, identify a loose pill, keep a medicine list,
// and check the list for warnings in official FDA labels.

// ---------- My medicines (saved only on this phone) ----------
function getMeds() { return store.get("medicines", []); }
function saveMeds(meds) { store.set("medicines", meds); updateMedsCount(); }

function addMed(name, strength = "") {
  const clean = name.trim().toLowerCase();
  if (!clean) return false;
  const meds = getMeds();
  if (meds.some((m) => m.name === clean)) return false;
  meds.push({ name: clean, strength });
  saveMeds(meds);
  return true;
}

function updateMedsCount() {
  const n = getMeds().length;
  $("meds-count").textContent = n ? `${n} saved · check them for warnings` : "Check them for warnings";
}
updateMedsCount();

screenHooks["pill-menu"] = () => { OCR.warmUp(); updateMedsCount(); };
screenHooks["pill-id"] = () => OCR.warmUp();
screenHooks.meds = renderMeds;

function renderMeds() {
  const meds = getMeds();
  const list = $("meds-list");
  list.innerHTML = "";
  meds.forEach((m) => {
    const li = el("li", "card");
    const words = el("div");
    words.append(el("div", "bold", titleCase(m.name)));
    if (m.strength) words.append(el("div", "small muted", m.strength));
    const remove = el("button", "btn remove", "Remove");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${m.name}`);
    remove.addEventListener("click", () => {
      saveMeds(getMeds().filter((x) => x.name !== m.name));
      renderMeds();
    });
    li.append(words, remove);
    list.append(li);
  });
  $("meds-empty").hidden = meds.length > 0;
  $("check-meds").disabled = meds.length < 2;
  $("check-meds").textContent = meds.length < 2 ? "Add 2 or more to check for warnings" : "Check for warnings";
}

// Suggestions while typing a name
let suggestTimer;
$("med-input").addEventListener("input", (e) => {
  clearTimeout(suggestTimer);
  const q = e.target.value.trim();
  $("med-error").hidden = true;
  if (q.length < 2) return;
  suggestTimer = setTimeout(async () => {
    try {
      const { suggestions } = await api(`/meds/suggest?q=${encodeURIComponent(q)}`, null, { timeoutMs: 8000 });
      const list = $("med-suggestions");
      list.innerHTML = "";
      suggestions.forEach((s) => { const opt = document.createElement("option"); opt.value = s.name; list.append(opt); });
    } catch (_) { /* suggestions are optional */ }
  }, 250);
});

function addFromInput() {
  const name = $("med-input").value;
  if (!name.trim()) {
    $("med-error").textContent = "Type a medicine name first.";
    $("med-error").hidden = false;
    return;
  }
  if (!addMed(name)) {
    $("med-error").textContent = "That medicine is already on your list.";
    $("med-error").hidden = false;
    return;
  }
  $("med-input").value = "";
  renderMeds();
}
$("add-med").addEventListener("click", addFromInput);
$("med-input").addEventListener("keydown", (e) => { if (e.key === "Enter") addFromInput(); });

// ---------- Read a pill bottle ----------
$("label-camera").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const job = startJob({ title: "Reading the label…", steps: ["Reading the words", "Finding the medicine"] });
  job.step(0, "active");
  try {
    const { text } = await OCR.read(file, {
      onProgress: (words, p) => job.say(p == null ? words : `${words} ${Math.round(p * 100)}%`),
    });
    if (!job.isCurrent()) return;
    if (text.replace(/[^A-Za-z]/g, "").length < 6) {
      showError("Hold the bottle closer so the label fills the photo, and use good light. Turn the bottle so the medicine name faces you.",
        { title: "We couldn't read the label", retry: () => $("label-camera").click() });
      return;
    }
    job.step(0, "done");
    job.step(1, "active");
    const found = await api("/meds/read-label", { text });
    if (job.isCurrent()) showLabelResult(found, text);
  } catch (err) {
    if (job.isCurrent()) showError(err.message, { retry: () => show("pill-menu") });
  }
});

function showLabelResult(found, rawText) {
  const box = $("label-meds");
  box.innerHTML = "";
  $("label-raw").textContent = rawText;

  if (!found.medicines.length) {
    $("label-title").textContent = "We didn't find a medicine name";
    const card = el("div", "card stack-8");
    card.append(
      el("p", "", "We read the label but couldn't match a medicine name. You can type it in on My medicines."),
      el("p", "small muted", "Check \"What we read\" below to see what the photo picked up.")
    );
    box.append(card);
  } else {
    $("label-title").textContent = found.medicines.length === 1 ? "On this label" : `${found.medicines.length} medicines on this label`;
    found.medicines.forEach((m) => {
      const card = el("div", "card card--shadow item-card");
      card.append(el("div", "item-title", titleCase(m.name) + (m.strength ? ` ${m.strength}` : "")));
      if (m.label_name.toLowerCase() !== m.name) card.append(el("div", "item-meta", `Label says: ${titleCase(m.label_name)}`));
      if (!m.exact) card.append(el("div", "item-meta", "The photo was a little unclear. Please check the name matches your bottle."));
      const add = el("button", "btn btn--shadow bg-mint");
      add.type = "button";
      const already = getMeds().some((x) => x.name === m.name);
      add.textContent = already ? "Already on my list ✓" : "Add to my medicines";
      add.disabled = already;
      add.addEventListener("click", () => {
        addMed(m.name, m.strength);
        add.textContent = "Added ✓";
        add.disabled = true;
      });
      card.append(add);
      box.append(card);
    });
  }

  $("label-directions").hidden = !found.directions;
  $("label-directions-text").textContent = found.directions;
  speechText.label = found.medicines.length
    ? found.medicines.map((m) => `${m.name} ${m.strength}`).join(". ") + ". " + (found.directions ? "Directions: " + found.directions : "")
    : "We didn't find a medicine name on this label.";
  show("label-result");
}

// ---------- Identify a loose pill ----------
const pillChoice = { color: "", shape: "" };

function setupChips(containerId, key) {
  const chips = $(containerId).querySelectorAll(".chip");
  chips.forEach((chip) => {
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.setAttribute("aria-pressed", "false"));
      chip.setAttribute("aria-pressed", "true");
      pillChoice[key] = chip.dataset[key];
    });
  });
}
setupChips("color-chips", "color");
setupChips("shape-chips", "shape");

$("pill-camera").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const status = $("imprint-status");
  status.hidden = false;
  status.textContent = "Reading the pill… this can take a few seconds.";
  try {
    const { text } = await OCR.read(file, {
      mode: "imprint",
      onProgress: (words, p) => { status.textContent = p == null ? words : `${words} ${Math.round(p * 100)}%`; },
    });
    const marks = (text.match(/[A-Z0-9]{1,8}/g) || []).slice(0, 3).join(" ");
    if (marks) {
      $("imprint").value = marks;
      status.textContent = `We read "${marks}". Please check it against the pill and fix it if needed.`;
    } else {
      status.textContent = "We couldn't read the marks from the photo. Please type them in.";
    }
  } catch (err) {
    status.textContent = err.message;
  }
});

$("find-pill").addEventListener("click", findPill);
$("imprint").addEventListener("keydown", (e) => { if (e.key === "Enter") findPill(); });

async function findPill() {
  const imprint = $("imprint").value.trim();
  $("pill-id-error").hidden = !!imprint;
  if (!imprint) { $("imprint").focus(); return; }

  const job = startJob({ title: "Looking up this pill…", steps: ["Searching the pill list"], note: false });
  job.step(0, "active");
  try {
    const body = { imprint };
    if (pillChoice.color) body.color = pillChoice.color;
    if (pillChoice.shape) body.shape = pillChoice.shape;
    const res = await api("/pills/identify", body);
    if (job.isCurrent()) showPillResults(res, imprint);
  } catch (err) {
    if (job.isCurrent()) showError(err.message, { retry: findPill });
  }
}

const MATCH_WORDS = {
  strong: ["Strong match", "bg-safe"],
  possible: ["Possible match", "bg-careful"],
  weak: ["Weak match", "bg-white"],
};

function showPillResults(res, imprint) {
  const box = $("pill-candidates");
  box.innerHTML = "";

  if (!res.available) {
    $("pill-results-title").textContent = "Pill lookup isn't set up yet";
    $("pill-results-sub").textContent = "The pill list hasn't been installed on the server. You can still read a pill bottle or add medicines by name.";
    show("pill-results");
    return;
  }
  if (!res.candidates.length) {
    $("pill-results-title").textContent = "No matches found";
    $("pill-results-sub").textContent = `We didn't find a pill marked "${imprint}". Check the letters and numbers on both sides and try again.`;
    show("pill-results");
    return;
  }

  $("pill-results-title").textContent = res.candidates.length === 1 ? "1 possible match" : `${res.candidates.length} possible matches`;
  $("pill-results-sub").textContent = `For a pill marked "${imprint}". The best match is first.`;

  res.candidates.forEach((p) => {
    const [matchWords, matchColor] = MATCH_WORDS[p.match] || MATCH_WORDS.weak;
    const card = el("div", "card item-card");
    card.append(el("span", `tag ${matchColor}`, matchWords));
    card.append(el("div", "item-title", `${p.name}${p.strength ? " " + p.strength : ""}`));
    const look = [`Marked "${p.imprint}"`, p.colors.join(" and "), p.shape].filter(Boolean).join(" · ");
    card.append(el("div", "item-meta", look));
    if (p.maker) card.append(el("div", "small muted", `Made by ${p.maker}`));
    const add = el("button", "btn btn--shadow bg-mint", "This is mine. Add to my medicines");
    add.type = "button";
    add.style.whiteSpace = "normal";
    add.addEventListener("click", () => {
      addMed(p.generic || p.name, p.strength); // the ingredient name works best for FDA label checks
      add.textContent = "Added ✓";
      add.disabled = true;
    });
    card.append(add);
    box.append(card);
  });
  show("pill-results");
}

// ---------- Check my medicines for warnings ----------
let lastWarnings = null;

$("check-meds").addEventListener("click", checkMeds);

async function checkMeds() {
  const meds = getMeds();
  if (meds.length < 2) return;
  const job = startJob({ title: "Checking your medicines…", steps: ["Getting the FDA labels", "Looking for warnings"], note: false });
  job.step(0, "active");
  job.say("This can take up to 20 seconds.");
  try {
    const res = await api("/meds/interactions", { medicines: meds.map((m) => m.name) }, { timeoutMs: 60000 });
    if (!job.isCurrent()) return;
    job.step(0, "done");
    showWarnings(res);
  } catch (err) {
    if (job.isCurrent()) showError(err.message, { retry: checkMeds });
  }
}

function showWarnings(res) {
  lastWarnings = res;
  const n = res.warnings.length;
  $("warn-summary").className = `card card--shadow verdict ${n ? "bg-careful" : "bg-safe"}`;
  $("warn-title").textContent = n ? `Ask your pharmacist about ${n} combination${n === 1 ? "" : "s"}` : "No warnings found on the labels";
  $("warn-sub").textContent = n
    ? "The official FDA labels for these medicines mention each other. That doesn't always mean you must stop; your doctor may have planned it. Ask your pharmacist."
    : `We checked the FDA labels for ${res.checked.length} medicines and they don't mention each other.`;

  const list = $("warn-list");
  list.innerHTML = "";
  const speech = [$("warn-title").textContent + "."];
  res.warnings.forEach((w) => {
    const card = el("div", "card item-card");
    card.append(el("div", "item-title", w.medicines.map(titleCase).join(" + ")));
    w.mentions.forEach((m) => {
      card.append(el("div", "item-meta bold", `The FDA label for ${titleCase(m.label_of)} says:`));
      card.append(el("blockquote", "quote", m.excerpt));
    });
    list.append(card);
    speech.push(`${w.medicines.join(" and ")}.`);
  });

  $("warn-missing").hidden = !res.no_label_found.length;
  $("warn-missing-names").textContent = res.no_label_found.map(titleCase).join(", ");
  speech.push("This is not a full safety check. Ask your pharmacist before changing any medicine.");
  speechText.warnings = speech.join(" ");
  show("med-warnings");
}

$("share-warnings").addEventListener("click", () => {
  if (!lastWarnings) return;
  const lines = lastWarnings.warnings.map((w) => `• ${w.medicines.map(titleCase).join(" + ")}`);
  shareText(
    lastWarnings.warnings.length
      ? `CareCircle found FDA label warnings to ask my pharmacist about:\n${lines.join("\n")}`
      : "CareCircle didn't find warnings between my medicines on their FDA labels."
  );
});
