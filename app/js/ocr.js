// Reads text from photos ON THE PHONE using Tesseract.js (bundled in app/vendor).
// Before reading, each photo is resized, turned gray, and given more contrast,
// which makes phone photos and screenshots much easier to read.

const OCR = (() => {
  const base = new URL("vendor/tesseract/", document.baseURI).href;
  let workerPromise = null;
  let listener = null; // called with progress messages while working

  const STATUS_WORDS = {
    "loading tesseract core": "Getting the text reader ready (first time only)…",
    "loading language traineddata": "Getting the text reader ready (first time only)…",
    "initializing api": "Getting the text reader ready…",
    "recognizing text": "Reading the words…",
  };

  function getWorker() {
    if (!window.Tesseract) {
      return Promise.reject(new Error("The text reader didn't load. Please reload the page."));
    }
    if (!workerPromise) {
      workerPromise = Tesseract.createWorker("eng", 1, {
        workerPath: base + "worker.min.js",
        corePath: base + "core",
        langPath: base + "lang",
        workerBlobURL: false,
        logger: (m) => {
          if (listener) listener(STATUS_WORDS[m.status] || "Getting ready…", m.status === "recognizing text" ? m.progress : null);
        },
      }).catch((err) => {
        workerPromise = null; // allow another try later
        throw err;
      });
    }
    return workerPromise;
  }

  // Start loading in the background so the first scan is faster.
  function warmUp() {
    getWorker().catch(() => {});
  }

  async function loadImage(file) {
    if (!file || !file.type || !file.type.startsWith("image/")) {
      throw new Error("That file isn't a photo. Please choose a photo or screenshot.");
    }
    try {
      // "from-image" turns sideways phone photos the right way up.
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (_) {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error("We couldn't open that photo. Try taking a screenshot of it, or take a new photo."));
        img.src = URL.createObjectURL(file);
      });
    }
  }

  async function prepare(file, { maxSide = 2200, minSide = 1400, autoInvert = true } = {}) {
    const img = await loadImage(file);
    const longest = Math.max(img.width, img.height);
    let scale = 1;
    if (longest > maxSide) scale = maxSide / longest;
    else if (longest < minSide) scale = Math.min(2.5, minSide / longest); // small screenshots read better larger

    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // Gray + stronger contrast. Dark-mode screenshots get flipped to dark text on light.
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const px = image.data;
    const hist = new Uint32Array(256);
    let total = 0;
    for (let i = 0; i < px.length; i += 4) {
      const g = (px[i] * 299 + px[i + 1] * 587 + px[i + 2] * 114) / 1000 | 0;
      px[i] = g;
      hist[g]++;
      total += g;
    }
    const count = px.length / 4;
    const invert = autoInvert && total / count < 100;
    let lo = 0, hi = 255, seen = 0;
    for (let v = 0; v < 256; v++) { seen += hist[v]; if (seen > count * 0.01) { lo = v; break; } }
    seen = 0;
    for (let v = 255; v >= 0; v--) { seen += hist[v]; if (seen > count * 0.01) { hi = v; break; } }
    const range = Math.max(1, hi - lo);
    for (let i = 0; i < px.length; i += 4) {
      let v = ((px[i] - lo) * 255) / range;
      v = v < 0 ? 0 : v > 255 ? 255 : v;
      if (invert) v = 255 - v;
      px[i] = px[i + 1] = px[i + 2] = v;
    }
    ctx.putImageData(image, 0, 0);
    return canvas;
  }

  // ---------- Straighten tilted photos ----------
  // Try small rotations and keep the one where the text lines line up best
  // (dark pixels bunch into rows). Screenshots come out at 0 and are left alone.
  function findTilt(canvas) {
    const scale = Math.min(1, 500 / Math.max(canvas.width, canvas.height));
    const w = Math.round(canvas.width * scale), h = Math.round(canvas.height * scale);
    const small = document.createElement("canvas");
    small.width = w; small.height = h;
    const sctx = small.getContext("2d", { willReadFrequently: true });
    sctx.drawImage(canvas, 0, 0, w, h);
    const px = sctx.getImageData(0, 0, w, h).data;
    const xs = [], ys = [];
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (px[(y * w + x) * 4] < 110) { xs.push(x - w / 2); ys.push(y - h / 2); }
      }
    }
    if (xs.length < 50) return 0;
    const diag = Math.ceil(Math.hypot(w, h));
    const score = (deg) => {
      const r = (deg * Math.PI) / 180, s = Math.sin(r), c = Math.cos(r);
      const rows = new Float64Array(diag + 2);
      for (let i = 0; i < xs.length; i++) {
        const row = Math.round(ys[i] * c - xs[i] * s + diag / 2);
        if (row >= 0 && row < rows.length) rows[row]++;
      }
      let total = 0;
      for (let i = 1; i < rows.length; i++) { const d = rows[i] - rows[i - 1]; total += d * d; }
      return total;
    };
    let best = 0, bestScore = score(0);
    for (let deg = -15; deg <= 15; deg += 1) { const s = score(deg); if (s > bestScore) { best = deg; bestScore = s; } }
    for (let deg = best - 0.75; deg <= best + 0.75; deg += 0.25) { const s = score(deg); if (s > bestScore) { best = deg; bestScore = s; } }
    return best;
  }

  function rotate(canvas, deg) {
    if (Math.abs(deg) < 0.5) return canvas;
    const r = (deg * Math.PI) / 180;
    const w = canvas.width, h = canvas.height;
    const nw = Math.round(Math.abs(w * Math.cos(r)) + Math.abs(h * Math.sin(r)));
    const nh = Math.round(Math.abs(w * Math.sin(r)) + Math.abs(h * Math.cos(r)));
    const out = document.createElement("canvas");
    out.width = nw; out.height = nh;
    const ctx = out.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, nw, nh);
    ctx.translate(nw / 2, nh / 2);
    ctx.rotate(-r);
    ctx.drawImage(canvas, -w / 2, -h / 2);
    return out;
  }

  // ---------- Pills: crop to the pill and blank out the table around it ----------
  function isolatePill(canvas) {
    const w = canvas.width, h = canvas.height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const image = ctx.getImageData(0, 0, w, h);
    const px = image.data;
    const t = otsu(px);
    // Bounding box of the bright area (the pill)
    const rowCount = new Uint32Array(h), colCount = new Uint32Array(w);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (px[(y * w + x) * 4] > t) { rowCount[y]++; colCount[x]++; }
    }
    const rows = [...rowCount.keys()].filter((y) => rowCount[y] > w * 0.03);
    const cols = [...colCount.keys()].filter((x) => colCount[x] > h * 0.03);
    if (!rows.length || !cols.length) return canvas;
    const pad = Math.round(Math.min(w, h) * 0.02);
    const x0 = Math.max(0, cols[0] - pad), x1 = Math.min(w, cols[cols.length - 1] + pad);
    const y0 = Math.max(0, rows[0] - pad), y1 = Math.min(h, rows[rows.length - 1] + pad);
    const cw = x1 - x0, ch = y1 - y0;
    const crop = ctx.getImageData(x0, y0, cw, ch);
    const cp = crop.data;
    // Flood-fill the dark background from the edges with white, so only the pill's marks stay dark.
    const seen = new Uint8Array(cw * ch);
    const stack = [];
    for (let x = 0; x < cw; x++) { stack.push(x, (ch - 1) * cw + x); }
    for (let y = 0; y < ch; y++) { stack.push(y * cw, y * cw + cw - 1); }
    while (stack.length) {
      const i = stack.pop();
      if (seen[i] || cp[i * 4] > t) continue;
      seen[i] = 1;
      cp[i * 4] = cp[i * 4 + 1] = cp[i * 4 + 2] = 255;
      const x = i % cw, y = (i / cw) | 0;
      if (x > 0) stack.push(i - 1);
      if (x < cw - 1) stack.push(i + 1);
      if (y > 0) stack.push(i - cw);
      if (y < ch - 1) stack.push(i + cw);
    }
    const out = document.createElement("canvas");
    out.width = cw; out.height = ch;
    out.getContext("2d").putImageData(crop, 0, 0);
    return out;
  }

  function otsu(px) {
    const hist = new Float64Array(256);
    for (let i = 0; i < px.length; i += 4) hist[px[i]]++;
    const total = px.length / 4;
    let sum = 0;
    for (let v = 0; v < 256; v++) sum += v * hist[v];
    let sumB = 0, wB = 0, best = 0, t = 127;
    for (let v = 0; v < 256; v++) {
      wB += hist[v];
      if (!wB) continue;
      const wF = total - wB;
      if (!wF) break;
      sumB += v * hist[v];
      const between = wB * wF * (sumB / wB - (sum - sumB) / wF) ** 2;
      if (between > best) { best = between; t = v; }
    }
    return t;
  }

  function scaled(canvas, longest) {
    const s = longest / Math.max(canvas.width, canvas.height);
    const out = document.createElement("canvas");
    out.width = Math.round(canvas.width * s);
    out.height = Math.round(canvas.height * s);
    out.getContext("2d").drawImage(canvas, 0, 0, out.width, out.height);
    return out;
  }

  function cleanText(text) {
    return text
      .replace(/([A-Za-z0-9])-\s*\n\s*(?=[a-z0-9])/g, "$1-") // rejoin words and links split across lines
      .split("\n")
      .map((line) => line.replace(/\s+/g, " ").trim())
      .filter((line) => {
        const letters = (line.match(/[A-Za-z0-9]/g) || []).length;
        return letters >= 2 && letters / line.length >= 0.5; // drop lines of stray marks
      })
      .join("\n");
  }

  function withTimeout(promise, ms) {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("Reading the photo took too long. Try a clearer, closer photo.")), ms);
      }),
    ]).finally(() => clearTimeout(timer));
  }

  // mode "text": messages, letters, labels.  mode "imprint": the marks stamped on a pill.
  async function read(file, { mode = "text", onProgress } = {}) {
    listener = onProgress || null;
    try {
      const worker = await withTimeout(getWorker(), 120000);
      if (mode === "imprint") return await readImprint(file, worker);

      let canvas = await prepare(file);
      canvas = rotate(canvas, findTilt(canvas));
      await worker.setParameters({ tessedit_pageseg_mode: "3", tessedit_char_whitelist: "" });
      const first = (await withTimeout(worker.recognize(canvas), 90000)).data;
      let best = { text: cleanText(first.text || ""), confidence: first.confidence || 0 };

      // Labels and photos sometimes read better as one block of text. Keep whichever is clearer.
      if (best.confidence < 80) {
        await worker.setParameters({ tessedit_pageseg_mode: "6" });
        const second = (await withTimeout(worker.recognize(canvas), 90000)).data;
        if ((second.confidence || 0) > best.confidence + 3) {
          best = { text: cleanText(second.text || ""), confidence: second.confidence };
        }
      }
      return best;
    } finally {
      listener = null;
    }
  }

  async function readImprint(file, worker) {
    // No dark-mode flip here: a light pill on a dark table should stay light.
    const pill = isolatePill(await prepare(file, { maxSide: 1200, minSide: 600, autoInvert: false }));
    await worker.setParameters({ tessedit_char_whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" });
    let best = { text: "", confidence: 0 };
    try {
      // Marks can be big or small in the photo, so try a few sizes and keep the clearest reading.
      for (const longest of [600, 360, 900]) {
        for (const psm of ["7", "11"]) {
          await worker.setParameters({ tessedit_pageseg_mode: psm });
          const { data } = await withTimeout(worker.recognize(scaled(pill, longest)), 60000);
          const text = (data.text || "").replace(/[^A-Z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
          if (text && data.confidence > best.confidence) best = { text, confidence: data.confidence };
        }
        if (best.confidence >= 80) break;
      }
    } finally {
      await worker.setParameters({ tessedit_char_whitelist: "" });
    }
    return best;
  }

  return { read, warmUp };
})();
