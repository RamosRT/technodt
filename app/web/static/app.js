/* Конверт-трек — scanner + HTMX glue */

"use strict";

// ─── Scanner state ──────────────────────────────────────────────
const App = {
  mode: "idle",          // idle | register | verify
  envelopeId: null,      // current envelope UUID
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
  const barcode = SCANNER.value.trim();
  SCANNER.value = "";
  if (!barcode) return;
  dispatch(barcode);
});

function dispatch(barcode) {
  if (App.mode === "idle") return;
  if (App.mode === "verify") {
    if (App.awaitingEnvBC) {
      openVerifyEnvelope(barcode);
    } else {
      scanDocInVerify(barcode);
    }
    return;
  }
  if (App.mode === "register") {
    addDocToEnvelope(barcode);
  }
}

// ─── Register mode ──────────────────────────────────────────────
function addDocToEnvelope(barcode) {
  if (!App.envelopeId) return;
  htmx.ajax("POST", `/ui/envelopes/${App.envelopeId}/documents`, {
    target: "#doc-area",
    swap: "outerHTML",
    values: { barcode },
  });
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
    target: "#verify-area",
    swap: "outerHTML",
    values: { barcode },
  });
}

// ─── Mode switching ─────────────────────────────────────────────
function setMode(mode) {
  App.mode = mode;
  App.envelopeId = null;
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
    hint && (hint.textContent = "Сканируйте документы или введите ШК вручную");
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
function onEnvelopeLoaded(id) {
  App.envelopeId = id;
  App.mode = "register";
  App.awaitingEnvBC = false;
  updateModeBar();
  ensureFocus();
}

function onVerifyEnvelopeLoaded(id) {
  App.envelopeId = id;
  App.awaitingEnvBC = false;
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
  const text = typeof detail === "string" ? detail
              : Array.isArray(detail) ? detail.map(d => d.msg || d).join("; ")
              : `Ошибка сервера (${status})`;
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
