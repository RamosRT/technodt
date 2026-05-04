/* Конверт-трек — scanner + HTMX glue */

"use strict";

// ─── Scanner state ──────────────────────────────────────────────
const App = {
  mode: "idle",          // idle | register | verify
  envelopeId: null,      // current envelope UUID
  envelopeBarcode: null, // current envelope barcode
  envelopeDocsCount: 0,  // current envelope document count
  verifyScannedCount: 0,
  verifyTotalCount: 0,
  awaitingEnvBC: false,  // true while waiting for envelope barcode in verify
};

const SCANNER = document.getElementById("scanner-input");

// Returns true when el is a visible user-facing input (not the hidden scanner itself)
function isUserInput(el) {
  if (!el || el === SCANNER) return false;
  const tag = el.tagName;
  return (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") && el.type !== "hidden";
}

// Steal focus back to scanner only when a real user-input is NOT active
document.addEventListener("click", (e) => {
  if (SCANNER && !isUserInput(e.target)) SCANNER.focus();
});
document.addEventListener("keydown", () => {
  if (SCANNER && !isUserInput(document.activeElement)) SCANNER.focus();
});

function ensureFocus() {
  if (App.mode === "idle") return;          // login screen — don't interfere
  if (isUserInput(document.activeElement)) return; // user is in a form field
  if (SCANNER && document.activeElement !== SCANNER) SCANNER.focus();
}
setInterval(ensureFocus, 500);

// ─── Scanner dispatch ───────────────────────────────────────────
SCANNER && SCANNER.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const barcode = sanitizeScannedInput(SCANNER.value);
  SCANNER.value = "";
  if (!barcode) return;
  dispatch(barcode);
});

function sanitizeScannedInput(value) {
  if (!value) return "";
  // Some scanners prepend AIM symbology IDs like ]C1 / ]e0.
  return value.trim().replace(/^\][A-Za-z][0-9]/, "");
}

function normalizeBarcodeForCompare(value) {
  if (!value) return "";
  // Compare loosely: ignore case and separators like spaces/hyphens.
  return value.toUpperCase().replace(/[^0-9A-Z]/g, "");
}

async function dispatch(barcode) {
  if (App.mode === "idle") return;
  if (App.mode === "verify") {
    if (App.awaitingEnvBC) {
      openVerifyEnvelope(barcode);
    } else {
      const scanned = normalizeBarcodeForCompare(barcode);
      const envelope = normalizeBarcodeForCompare(App.envelopeBarcode);
      if (envelope && (scanned === envelope || scanned.includes(envelope) || envelope.includes(scanned))) {
        const allScanned = App.verifyScannedCount >= App.verifyTotalCount;
        if (!allScanned) {
          const ok = window.confirm("Не все документы отсканированы. Вы уверены что желаете завершить проверку?");
          if (!ok) return;
        }
        finishVerify(!allScanned);
        return;
      }
      scanDocInVerify(barcode);
    }
    return;
  }
  if (App.mode === "register") {
    // In register mode scanning the current envelope barcode means "start sealing".
    const scanned = normalizeBarcodeForCompare(barcode);
    const envelope = normalizeBarcodeForCompare(App.envelopeBarcode);
    if (envelope && (scanned === envelope || scanned.includes(envelope) || envelope.includes(scanned))) {
      if (App.envelopeDocsCount < 1) {
        showToast("Нельзя запечатать пустой конверт: сначала добавьте документ", "error");
        return;
      }
      openModal("seal-modal");
      showToast("ШК конверта распознан — заполните поля и запечатайте", "info");
      return;
    }
    if (await openDraftEnvelopeForPacking(barcode)) return;
    addDocToEnvelope(barcode);
  }
}

// ─── Register mode ──────────────────────────────────────────────
function addDocToEnvelope(barcode) {
  if (!App.envelopeId) return;
  htmx.ajax("POST", `/ui/envelopes/${App.envelopeId}/documents`, {
    target: "#envelope-card",
    swap: "outerHTML",
    values: { barcode },
  });
}

async function openDraftEnvelopeForPacking(barcode) {
  let response;
  try {
    response = await fetch(`/api/envelopes/by-barcode/${encodeURIComponent(barcode)}`, {
      headers: { "Accept": "application/json" },
    });
  } catch (_) {
    return false;
  }

  if (response.status === 404) return false;

  let envelope;
  try {
    envelope = await response.json();
  } catch (_) {
    showToast("Не удалось прочитать данные конверта", "error");
    return true;
  }

  if (!response.ok) {
    showToast(envelope.detail || "Не удалось открыть конверт", "error");
    return true;
  }

  if (envelope.id === App.envelopeId) return false;

  if (envelope.status !== "draft") {
    showToast("Продолжить заполнение можно только для конверта в статусе «Черновик»", "error");
    return true;
  }

  htmx.ajax("GET", `/ui/envelopes/${envelope.id}/card`, {
    target: document.getElementById("envelope-card") ? "#envelope-card" : "#main-area",
    swap: document.getElementById("envelope-card") ? "outerHTML" : "innerHTML",
  });
  showToast(`Открыт черновик ${envelope.number}`, "info");
  return true;
}

// ─── Verify mode ────────────────────────────────────────────────
function openVerifyEnvelope(barcode) {
  htmx.ajax("GET", `/ui/verify/start-by-barcode?barcode=${encodeURIComponent(barcode)}`, {
    target: "#main-area",
    swap: "innerHTML",
  });
}

function scanDocInVerify(barcode) {
  if (!App.envelopeId) return;
  htmx.ajax("POST", `/ui/envelopes/${App.envelopeId}/verify/scan`, {
    target: "#verify-card",
    swap: "outerHTML",
    values: { barcode },
  });
}

function finishVerify(force) {
  if (!App.envelopeId) return;
  htmx.ajax("POST", `/ui/envelopes/${App.envelopeId}/verify/finish`, {
    target: "#verify-card",
    swap: "outerHTML",
    values: { force: force ? "true" : "false" },
  });
}

// ─── Mode switching ─────────────────────────────────────────────
function setMode(mode) {
  App.mode = mode;
  App.envelopeId = null;
  App.envelopeBarcode = null;
  App.envelopeDocsCount = 0;
  App.verifyScannedCount = 0;
  App.verifyTotalCount = 0;
  App.awaitingEnvBC = (mode === "verify");
  updateModeBar();
}

function updateModeBar() {
  const bar = document.getElementById("mode-bar-name");
  const hint = document.getElementById("mode-bar-hint");
  if (!bar) return;
  bar.className = "mode-name";
  if (App.mode === "idle") {
    bar.textContent = "Ожидание";
    hint && (hint.textContent = "");
  } else if (App.mode === "register") {
    bar.classList.add("mode-register");
    bar.textContent = "Регистрация";
    hint && (hint.textContent = "Сканируйте документы или ШК черновика");
  } else if (App.mode === "verify") {
    bar.classList.add("mode-verify");
    if (App.awaitingEnvBC) {
      bar.textContent = "Верификация";
      hint && (hint.textContent = "Отсканируйте ШК конверта");
    } else {
      bar.textContent = "Верификация";
      hint && (hint.textContent = "Сканируйте документы из конверта");
    }
  }
}

// Called by server-rendered HTML after envelope is created/loaded
function onEnvelopeLoaded(id, barcode = null, docsCount = 0) {
  App.envelopeId = id;
  App.envelopeBarcode = barcode;
  App.envelopeDocsCount = Number.isFinite(Number(docsCount)) ? Number(docsCount) : 0;
  App.mode = "register";
  App.awaitingEnvBC = false;
  updateModeBar();
  // The callback is invoked from an inline script inside an HTMX fragment.
  // Defer rendering so the <svg id="env-bc-svg"> is already in the DOM.
  if (barcode) requestAnimationFrame(() => renderEnvelopeBarcode(barcode));
  ensureFocus();
}

function onVerifyEnvelopeLoaded(id, barcode = null, scannedCount = 0, totalCount = 0) {
  App.envelopeId = id;
  App.envelopeBarcode = barcode;
  App.verifyScannedCount = Number.isFinite(Number(scannedCount)) ? Number(scannedCount) : 0;
  App.verifyTotalCount = Number.isFinite(Number(totalCount)) ? Number(totalCount) : 0;
  App.awaitingEnvBC = false;
  App.mode = "verify";
  updateModeBar();
  ensureFocus();
}

// ─── Flash feedback ─────────────────────────────────────────────
function flashRow(rowId) {
  const el = document.getElementById(rowId);
  if (!el) return;
  el.classList.remove("scan-flash");
  void el.offsetWidth; // reflow
  el.classList.add("scan-flash");
}

// ─── HTMX event hooks ───────────────────────────────────────────
document.addEventListener("htmx:responseError", (e) => {
  const status = e.detail.xhr.status;
  const msg = e.detail.xhr.responseText;
  let parsed;
  try { parsed = JSON.parse(msg); } catch (_) {}
  const detail = parsed?.detail;
  // UI routes often return an HTML fragment for errors, not JSON.
  const plain = (msg || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  const text = typeof detail === "string" ? detail
              : Array.isArray(detail) ? detail.map(d => d.msg || d).join("; ")
              : plain || `Ошибка сервера (${status})`;
  showToast(text, "error");
});

// ─── Toast notifications ────────────────────────────────────────
function showToast(msg, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    Object.assign(container.style, {
      position: "fixed", bottom: "24px", right: "24px",
      display: "flex", flexDirection: "column", gap: "8px", zIndex: "9999",
    });
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `alert alert-${type === "error" ? "error" : type === "success" ? "success" : "info"}`;
  toast.textContent = msg;
  Object.assign(toast.style, { minWidth: "260px", boxShadow: "0 4px 16px rgba(0,0,0,.2)" });
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ─── Modal helpers ──────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id)?.removeAttribute("hidden");
  ensureFocus();
}
function closeModal(id) {
  document.getElementById(id)?.setAttribute("hidden", "");
  ensureFocus();
}

// ─── Manual barcode input ───────────────────────────────────────
function submitManualBarcode(formId) {
  const form = document.getElementById(formId);
  if (!form) return;
  const input = form.querySelector("input[name=barcode]");
  if (!input || !input.value.trim()) return;
  dispatch(input.value.trim());
  input.value = "";
}

// ─── Row action menu placement ───────────────────────────────────
document.addEventListener("toggle", (e) => {
  const menu = e.target;
  if (!(menu instanceof HTMLDetailsElement) || !menu.classList.contains("row-menu")) return;
  if (!menu.open) {
    return;
  }
  const panel = menu.querySelector(".row-menu-panel");
  const trigger = menu.querySelector(".row-menu-trigger");
  if (!panel) return;
  const rect = (trigger || menu).getBoundingClientRect();
  const panelHeight = panel.offsetHeight || 220;
  const panelWidth = panel.offsetWidth || 210;
  const canOpenDown = rect.bottom + 8 + panelHeight <= window.innerHeight - 8;
  const top = canOpenDown ? rect.bottom + 6 : Math.max(8, rect.top - panelHeight - 6);
  const left = Math.max(8, Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - 8));
  panel.style.top = `${Math.round(top)}px`;
  panel.style.left = `${Math.round(left)}px`;
}, true);

// ─── Envelope barcode rendering (Code128C SVG) ─────────────────
const CODE128_PATTERNS = [
  "212222","222122","222221","121223","121322","131222","122213","122312","132212","221213","221312",
  "231212","112232","122132","122231","113222","123122","123221","223211","221132","221231","213212",
  "223112","312131","311222","321122","321221","312212","322112","322211","212123","212321","232121",
  "111323","131123","131321","112313","132113","132311","211313","231113","231311","112133","112331",
  "132131","113123","113321","133121","313121","211331","231131","213113","213311","213131","311123",
  "311321","331121","312113","312311","332111","314111","221411","431111","111224","111422","121124",
  "121421","141122","141221","112214","112412","122114","122411","142112","142211","241211","221114",
  "413111","241112","134111","111242","121142","121241","114212","124112","124211","411212","421112",
  "421211","212141","214121","412121","111143","111341","131141","114113","114311","411113","411311",
  "113141","114131","311141","411131","211412","211214","211232","2331112"
];

function renderEnvelopeBarcode(data) {
  const svg = document.getElementById("env-bc-svg");
  if (!svg || !data) return;

  // Prefer Code 128C for even-length numeric payloads, otherwise fallback to 128B.
  const codeSet = /^\d+$/.test(data) && data.length % 2 === 0 ? "C" : "B";
  const values = [codeSet === "C" ? 105 : 104];
  if (codeSet === "C") {
    for (let i = 0; i < data.length; i += 2) values.push(parseInt(data.slice(i, i + 2), 10));
  } else {
    for (const ch of data) {
      const code = ch.charCodeAt(0);
      if (code < 32 || code > 126) return;
      values.push(code - 32);
    }
  }

  let checksum = values[0];
  for (let i = 1; i < values.length; i++) checksum += values[i] * i;
  values.push(checksum % 103, 106); // checksum + stop

  const module = 3;
  const height = 96;
  const quiet = 12 * module;
  let x = quiet;
  let bars = "";
  for (const code of values) {
    const pattern = CODE128_PATTERNS[code];
    if (!pattern) return;
    for (let i = 0; i < pattern.length; i++) {
      const w = parseInt(pattern[i], 10) * module;
      if (i % 2 === 0) bars += `<rect x="${x}" y="0" width="${w}" height="${height}" fill="#111"/>`;
      x += w;
    }
  }
  x += quiet;
  svg.setAttribute("viewBox", `0 0 ${x} ${height}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", String(height));
  svg.innerHTML = bars;
}
