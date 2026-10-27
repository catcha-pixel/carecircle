// Call or text someone: people the user trusts, saved only on this phone.
// Uses the phone's own Phone and Messages apps (tel: and sms: links). Nothing is sent automatically.

let contactMessage = ""; // filled in when opened from a result, so a text can say what it's about

function getContacts() { return store.get("contacts", []); }
function saveContacts(list) { store.set("contacts", list); }

// Keep a leading + and the digits: "(555) 123-4567" -> "5551234567"
function cleanPhone(raw) {
  const trimmed = raw.trim();
  return (trimmed.startsWith("+") ? "+" : "") + trimmed.replace(/\D/g, "");
}

function prettyPhone(phone) {
  const d = phone.replace(/\D/g, "");
  if (d.length === 10) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
  if (d.length === 11 && d[0] === "1") return `(${d.slice(1, 4)}) ${d.slice(4, 7)}-${d.slice(7)}`;
  return phone;
}

function smsLink(phone, body) {
  // "?&body=" works on both iPhone and Android.
  return body ? `sms:${phone}?&body=${encodeURIComponent(body)}` : `sms:${phone}`;
}

// Opening from a result screen pre-writes the text message.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-contact-about]");
  if (!btn) return;
  if (btn.dataset.contactAbout === "result" && typeof lastScam !== "undefined" && lastScam) {
    const r = lastScam.result;
    contactMessage = `Can you help me check a message I got? CareCircle says "${r.title}" (${r.confidence}). It said: "${lastScam.text.slice(0, 300)}"`;
  } else if (btn.dataset.contactAbout === "warnings" && typeof lastWarnings !== "undefined" && lastWarnings) {
    const pairs = lastWarnings.warnings.map((w) => w.medicines.map(titleCase).join(" + ")).join("; ");
    contactMessage = pairs
      ? `Can you help me with my medicines? CareCircle found FDA label warnings about: ${pairs}.`
      : "Can you help me look over my medicines?";
  }
  show("contacts");
});

// Opening from Home starts with a blank message.
document.querySelector('#home [data-go="contacts"]').addEventListener("click", () => {
  contactMessage = "";
  renderContacts();
});

screenHooks.contacts = renderContacts;

function renderContacts() {
  const contacts = getContacts();
  const about = $("contacts-about");
  about.hidden = !contactMessage;
  about.textContent = contactMessage ? "Tap Text to send them a message about what you just checked. You can change the words before you send it." : "";

  const list = $("contacts-list");
  list.innerHTML = "";
  contacts.forEach((c, i) => {
    const li = el("li", "card contact");
    const top = el("div", "contact-top");
    const who = el("div");
    who.append(el("div", "item-title", c.name), el("div", "item-meta", prettyPhone(c.phone)));
    const remove = el("button", "btn remove", "Remove");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${c.name}`);
    remove.addEventListener("click", () => {
      if (!confirm(`Remove ${c.name}?`)) return;
      saveContacts(getContacts().filter((_, j) => j !== i));
      renderContacts();
    });
    top.append(who, remove);

    const actions = el("div", "grid-2");
    const call = el("a", "btn btn--shadow bg-mint");
    call.href = `tel:${c.phone}`;
    call.setAttribute("aria-label", `Call ${c.name}`);
    call.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/></svg>';
    call.append(el("span", "", "Call"));
    const text = el("a", "btn btn--shadow");
    text.href = smsLink(c.phone, contactMessage);
    text.setAttribute("aria-label", `Text ${c.name}`);
    text.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>';
    text.append(el("span", "", "Text"));
    actions.append(call, text);

    li.append(top, actions);
    list.append(li);
  });

  $("contacts-empty").hidden = contacts.length > 0;
  $("add-contact-box").open = contacts.length === 0; // show the form right away the first time
}

$("add-contact").addEventListener("click", () => {
  const name = $("contact-name").value.trim();
  const phone = cleanPhone($("contact-phone").value);
  const digits = phone.replace(/\D/g, "").length;
  const error = $("contact-error");

  if (!name) { error.textContent = "Please type a name."; error.hidden = false; $("contact-name").focus(); return; }
  if (digits < 7 || digits > 15) {
    error.textContent = "Please type the full phone number, including the area code.";
    error.hidden = false;
    $("contact-phone").focus();
    return;
  }
  const contacts = getContacts();
  if (contacts.some((c) => c.phone === phone)) {
    error.textContent = "That number is already saved.";
    error.hidden = false;
    return;
  }
  contacts.push({ name, phone });
  saveContacts(contacts);
  error.hidden = true;
  $("contact-name").value = "";
  $("contact-phone").value = "";
  $("add-contact-box").open = false;
  renderContacts();
});
