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

let audioCtx = null;
let audioEnabled = false;

function unlockAudio() {
  if (audioEnabled) return;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audioCtx = audioCtx || new Ctx();
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    audioEnabled = true;
  } catch (_) {
    // Silent fallback: UI should keep working even if audio is unavailable.
  }
}

document.addEventListener("pointerdown", unlockAudio, { once: true });
document.addEventListener("keydown", unlockAudio, { once: true });

function beep(freq = 880, durationMs = 90, type = "sine", volume = 0.05) {
  if (!audioEnabled || !audioCtx) return;
  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, now);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(volume, now + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + durationMs / 1000);
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(now);
  osc.stop(now + durationMs / 1000 + 0.02);
}

function playFeedback(kind) {
  if (kind === "success") {
    beep(880, 70, "triangle", 0.045);
    setTimeout(() => beep(1175, 85, "triangle", 0.045), 80);
    return;
  }
  if (kind === "error") {
    beep(300, 120, "sawtooth", 0.06);
  }
}

// Returns true when el is a visible user-facing input (not the hidden scanner itself)
function isUserInput(el) {
  if (!el || el === SCANNER) return false;
  const tag = el.tagName;
  return (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") && el.type !== "hidden";
}

function scannerFocusEnabled() {
  return isLoginScreen() || App.mode === "register" || App.mode === "verify";
}

function isLoginScreen() {
  return document.body && document.body.classList.contains("is-login");
}

// Steal focus back to scanner only when a real user-input is NOT active
document.addEventListener("click", (e) => {
  if (!scannerFocusEnabled()) return;
  if (SCANNER && !isUserInput(e.target)) SCANNER.focus();
});
document.addEventListener("keydown", () => {
  if (!scannerFocusEnabled()) return;
  if (SCANNER && !isUserInput(document.activeElement)) SCANNER.focus();
});

// ─── Server time clock (for admin strip) ────────────────────────────────
function initServerClock() {
  const el = document.getElementById("server-time");
  if (!el) return;
  const iso = el.getAttribute("data-server-iso");
  if (!iso) return;
  const server0Ms = Date.parse(iso);
  if (Number.isNaN(server0Ms)) return;
  const client0Ms = Date.now();

  const pad2 = (n) => String(n).padStart(2, "0");
  // Render in local timezone (server_time provided as UTC ISO, but Date() converts
  // to the browser's local timezone).
  const formatLocal = (d) =>
    `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())} ` +
    `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()}`;

  const tick = () => {
    const serverNowMs = server0Ms + (Date.now() - client0Ms);
    el.textContent = formatLocal(new Date(serverNowMs));
  };

  tick();
  setInterval(tick, 1000);
}

document.addEventListener("DOMContentLoaded", initServerClock);
document.body.addEventListener("htmx:afterSwap", initServerClock);

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
  if (handleLoginQrScan(barcode)) return;
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

function parseLoginCandidateTokens(raw) {
  const candidate = (raw || "").trim();
  if (!candidate) return { server: "", username: "", pin: "" };
  if (candidate.includes("=") && !candidate.includes("|")) {
    const kv = {};
    candidate.split(/[&;\n]/).forEach((token) => {
      const idx = token.indexOf("=");
      if (idx <= 0 || idx >= token.length - 1) return;
      const key = token.slice(0, idx).trim().toLowerCase();
      const value = token.slice(idx + 1).trim();
      kv[key] = value;
    });
    return {
      server: kv.server || kv.server_url || kv.url || kv.host || "",
      username: kv.username || kv.user || kv.operator || kv.login || "",
      pin: kv.pin || kv.password || kv.code || "",
    };
  }
  const parts = candidate.split("|").map((p) => p.trim());
  if (parts.length === 4) {
    return { server: parts[1], username: parts[2], pin: parts[3] };
  }
  return { server: "", username: "", pin: "" };
}

function fixMistypedRuLayout(value) {
  const map = {
    й: "q", ц: "w", у: "e", к: "r", е: "t", н: "y", г: "u", ш: "i", щ: "o", з: "p", х: "[", ъ: "]",
    ф: "a", ы: "s", в: "d", а: "f", п: "g", р: "h", о: "j", л: "k", д: "l", ж: ";", э: "'",
    я: "z", ч: "x", с: "c", м: "v", и: "b", т: "n", ь: "m", б: ",", ю: ".",
    Й: "Q", Ц: "W", У: "E", К: "R", Е: "T", Н: "Y", Г: "U", Ш: "I", Щ: "O", З: "P", Х: "{", Ъ: "}",
    Ф: "A", Ы: "S", В: "D", А: "F", П: "G", Р: "H", О: "J", Л: "K", Д: "L", Ж: ":", Э: "\"",
    Я: "Z", Ч: "X", С: "C", М: "V", И: "B", Т: "N", Ь: "M", Б: "<", Ю: ">",
  };
  return String(value || "")
    .split("")
    .map((ch) => map[ch] || ch)
    .join("");
}

function decodeCp1251Utf8Mojibake(value) {
  const cp1251ExtendedMap = {
    "\u0402": 0x80, "\u0403": 0x81, "\u201A": 0x82, "\u0453": 0x83,
    "\u201E": 0x84, "\u2026": 0x85, "\u2020": 0x86, "\u2021": 0x87,
    "\u20AC": 0x88, "\u2030": 0x89, "\u0409": 0x8a, "\u2039": 0x8b,
    "\u040A": 0x8c, "\u040C": 0x8d, "\u040B": 0x8e, "\u040F": 0x8f,
    "\u0452": 0x90, "\u2018": 0x91, "\u2019": 0x92, "\u201C": 0x93,
    "\u201D": 0x94, "\u2022": 0x95, "\u2013": 0x96, "\u2014": 0x97,
    "\u2122": 0x99, "\u0459": 0x9a, "\u203A": 0x9b, "\u045A": 0x9c,
    "\u045C": 0x9d, "\u045B": 0x9e, "\u045F": 0x9f, "\u040E": 0xa1,
    "\u045E": 0xa2, "\u0408": 0xa3, "\u0490": 0xa5, "\u0401": 0xa8,
    "\u0404": 0xaa, "\u0407": 0xaf, "\u0406": 0xb2, "\u0456": 0xb3,
    "\u0491": 0xb4, "\u0451": 0xb8, "\u2116": 0xb9, "\u0454": 0xba,
    "\u0458": 0xbc, "\u0405": 0xbd, "\u0455": 0xbe, "\u0457": 0xbf,
  };
  const cp1251Byte = (ch) => {
    const code = ch.charCodeAt(0);
    if (code <= 0x7f) return code;
    if (cp1251ExtendedMap[ch] != null) return cp1251ExtendedMap[ch];
    if (code <= 0x00ff) return code;
    if (code >= 0x0410 && code <= 0x044f) return code - 0x350;
    return null;
  };
  const bytes = [];
  for (const ch of String(value || "")) {
    const b = cp1251Byte(ch);
    if (b == null) return String(value || "");
    bytes.push(b);
  }
  try {
    const decoded = new TextDecoder("utf-8").decode(new Uint8Array(bytes));
    return decoded || String(value || "");
  } catch (_) {
    return String(value || "");
  }
}

function parseLoginQr(raw) {
  const trimmed = (raw || "").trim();
  if (!trimmed) return null;
  const withoutAim = /^\][A-Za-z]\d/.test(trimmed) ? trimmed.slice(3) : trimmed;
  const normalized = withoutAim.replace(/\u0000/g, " ").trim();
  const direct = normalized.split("|").map((p) => p.trim());
  const isLegacy = direct.length === 4 && direct[0].toUpperCase() === "KTLOGIN";
  const legacy = isLegacy
    ? { server: direct[1], username: direct[2], pin: direct[3] }
    : { server: "", username: "", pin: "" };

  let uri = { server: "", username: "", pin: "" };
  if (/^ktlogin:\/\//i.test(normalized)) {
    const query = normalized.includes("?") ? normalized.split("?").slice(1).join("?") : "";
    try {
      uri = parseLoginCandidateTokens(decodeURIComponent(query));
    } catch (_) {
      uri = { server: "", username: "", pin: "" };
    }
  }
  const slashParts = normalized.split("/").map((p) => p.trim());
  const slashTag = fixMistypedRuLayout(slashParts[0] || "").toUpperCase();
  const slashCandidate = slashParts.length >= 4 && slashTag === "KTLOGIN"
    ? {
        server: fixMistypedRuLayout(slashParts[1] || "")
          .replace("..", "//")
          .replace(/>/g, "/")
          .replace(/^\s*h..p:\/\//i, "http://")
          .replace(/^\s*https:\/\//i, "https://"),
        username: decodeCp1251Utf8Mojibake(slashParts[2] || ""),
        pin: (slashParts[3] || "").trim(),
      }
    : { server: "", username: "", pin: "" };
  const keyValue = parseLoginCandidateTokens(normalized);
  const picked = legacy.server ? legacy : (uri.server ? uri : (slashCandidate.server ? slashCandidate : keyValue));
  const pin = (picked.pin || "").trim();
  const username = (picked.username || "").trim();
  const server = (picked.server || "").trim();
  if (!server || !username || !/^\d{4}$/.test(pin)) return null;
  return { serverUrl: server, username, password: pin };
}

function handleLoginQrScan(raw) {
  if (!isLoginScreen()) return false;
  const form = document.querySelector('form[hx-post="/ui/operator"]');
  const nameInput = document.getElementById("op-name");
  const passInput = document.getElementById("op-password");
  if (!form || !nameInput || !passInput) return false;
  const qr = parseLoginQr(raw);
  if (!qr) {
    showToast("QR входа не распознан", "error");
    return true;
  }
  nameInput.value = qr.username;
  passInput.value = qr.password;
  if (typeof form.requestSubmit === "function") form.requestSubmit();
  else form.submit();
  return true;
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

async function printZplLabel(envelopeId, printerId) {
  const normalizedPrinterId = String(printerId || "").trim();
  if (!normalizedPrinterId) {
    showToast("Выберите ZPL-принтер в Настройках", "error");
    return;
  }
  try {
    const response = await fetch(
      `/api/envelopes/${encodeURIComponent(envelopeId)}/print/label/send?printer_id=${encodeURIComponent(normalizedPrinterId)}`,
      { method: "POST" }
    );
    if (!response.ok) {
      let detail = "";
      try {
        const data = await response.json();
        detail = data?.detail || "";
      } catch (_) {
        detail = "";
      }
      showToast(detail || "Не удалось отправить этикетку на принтер", "error");
      return;
    }
    showToast("Этикетка отправлена на принтер", "success");
  } catch (_) {
    showToast("Ошибка сети при отправке на принтер", "error");
  }
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

document.addEventListener("htmx:afterRequest", (e) => {
  if (!e?.detail?.successful) return;
  const path = e.detail.requestConfig?.path || e.detail.pathInfo?.requestPath || "";
  const method = String(
    e.detail.requestConfig?.verb || e.detail.requestConfig?.method || ""
  ).toUpperCase();
  if (!path) return;
  const isEnvelopeSeal = method === "POST" && path.endsWith("/seal");
  const isVerifyFinish = method === "POST" && path.endsWith("/verify/finish");
  if (isEnvelopeSeal || isVerifyFinish) {
    playFeedback("success");
  }
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
  if (type === "error" || type === "success") {
    playFeedback(type);
  }
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

function escapeAttr(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function editBranchFromAdmin(btn) {
  const id = btn?.dataset?.id;
  if (!id) return;
  const name = btn.dataset.name || "";
  const title = document.getElementById("admin-edit-title");
  const body = document.getElementById("admin-edit-body");
  if (!title || !body) return;
  title.textContent = "Изменить филиал";
  body.innerHTML = `
    <form hx-patch="/ui/admin/branches/${id}" hx-target="#main-area" onsubmit="closeModal('admin-edit-modal')">
      <div class="form-row">
        <label>Название</label>
        <input class="form-control" name="name" value="${escapeAttr(name)}" required autofocus>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="closeModal('admin-edit-modal')">Отмена</button>
        <button type="submit" class="btn btn-primary">Сохранить</button>
      </div>
    </form>`;
  if (window.htmx) htmx.process(body);
  openModal("admin-edit-modal");
}

function editSignerFromAdmin(btn) {
  const id = btn?.dataset?.id;
  if (!id) return;
  const lastName = btn.dataset.lastName || "";
  const firstName = btn.dataset.firstName || "";
  const title = document.getElementById("admin-edit-title");
  const body = document.getElementById("admin-edit-body");
  if (!title || !body) return;
  title.textContent = "Изменить подписанта";
  body.innerHTML = `
    <form hx-patch="/ui/admin/signers/${id}" hx-target="#main-area" onsubmit="closeModal('admin-edit-modal')">
      <div class="admin-printer-form-grid">
        <div class="form-row">
          <label>Фамилия</label>
          <input class="form-control" name="last_name" value="${escapeAttr(lastName)}" required autofocus>
        </div>
        <div class="form-row">
          <label>Имя</label>
          <input class="form-control" name="first_name" value="${escapeAttr(firstName)}" required>
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="closeModal('admin-edit-modal')">Отмена</button>
        <button type="submit" class="btn btn-primary">Сохранить</button>
      </div>
    </form>`;
  if (window.htmx) htmx.process(body);
  openModal("admin-edit-modal");
}

window.editBranchFromAdmin = editBranchFromAdmin;
window.editSignerFromAdmin = editSignerFromAdmin;
window.printZplLabel = printZplLabel;

document.addEventListener("click", (e) => {
  const trigger = e.target?.closest?.("[data-admin-edit]");
  if (!trigger) return;
  e.preventDefault();
  if (trigger.dataset.adminEdit === "branch") {
    editBranchFromAdmin(trigger);
  } else if (trigger.dataset.adminEdit === "signer") {
    editSignerFromAdmin(trigger);
  }
});

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
