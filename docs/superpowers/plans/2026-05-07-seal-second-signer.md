# Seal Envelope: Second Signatory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the full seal dialog (3 dropdowns) with a single "Подписант №2" picker on both web and TSD, pulling Signer 1 and branch silently from operator settings.

**Architecture:** Template-level defaults — `_envelope_card_context` loads the operator row and passes it to Jinja2; the template uses hidden inputs for the pre-set values. Android `RegisterScreen` adds a `SelectionSheet` that appears before the seal API call.

**Tech Stack:** Python / FastAPI / Jinja2 (web), Kotlin / Jetpack Compose / Retrofit (Android)

---

## Files Changed

| File | Change |
|---|---|
| `app/routers/ui/pages.py` | `_envelope_card_context` loads `operator_row` and passes it to template context |
| `app/web/templates/partials/envelope_card.html` | Seal button disabled logic + seal modal form replaced |
| `android/app/src/main/java/ru/technoavia/konverttrack/MainActivity.kt` | `RegisterScreen` gets signer picker sheet before sealing |

No new files. No DB migrations. No API changes.

---

## Task 1: Backend — pass `operator_row` to envelope card template

**Files:**
- Modify: `app/routers/ui/pages.py:274–292`

### Step 1.1 — Open `pages.py` and locate `_envelope_card_context`

The function starts at line 274. Current body:

```python
async def _envelope_card_context(
    session: AsyncSession,
    *,
    envelope,
    operator: str | None,
    is_admin: bool,
) -> dict:
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)
    return {
        "envelope": envelope,
        "documents": envelope.documents,
        "branches": branches,
        "signers": signers,
        "status_labels": STATUS_LABELS,
        "operator": operator,
        "is_admin": is_admin,
        "audit_events": await _audit_events(session, envelope.id),
    }
```

### Step 1.2 — Replace the function body

```python
async def _envelope_card_context(
    session: AsyncSession,
    *,
    envelope,
    operator: str | None,
    is_admin: bool,
) -> dict:
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)
    operator_row = None
    if operator:
        operator_row = (
            await session.execute(select(Operator).where(Operator.username == operator))
        ).scalar_one_or_none()
    return {
        "envelope": envelope,
        "documents": envelope.documents,
        "branches": branches,
        "signers": signers,
        "status_labels": STATUS_LABELS,
        "operator": operator,
        "operator_row": operator_row,
        "is_admin": is_admin,
        "audit_events": await _audit_events(session, envelope.id),
    }
```

`Operator` is already imported at line 31. `select` is already imported at line 11. No new imports needed.

- [ ] Apply the edit above.

### Step 1.3 — Verify the server starts without errors

```bash
cd E:/technodt
venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Expected: server starts, no import errors, no tracebacks.

- [ ] Confirm server starts cleanly.

### Step 1.4 — Smoke-test: open an envelope card in the browser

Navigate to the web UI, create or open a draft envelope. The page should render normally (no Jinja2 errors). The seal modal still shows the old 3-dropdown form at this point — that's fine, template changes come in Task 2.

- [ ] Page renders without 500 errors.

### Step 1.5 — Commit

```bash
git add app/routers/ui/pages.py
git commit -m "feat: pass operator_row to envelope card template context"
```

- [ ] Commit done.

---

## Task 2: Web UI — simplify seal modal

**Files:**
- Modify: `app/web/templates/partials/envelope_card.html:63–211`

### Step 2.1 — Update the "Запечатать" button (around line 63)

Find this block:

```html
  <button class="btn btn-primary"
          onclick="document.getElementById('seal-modal').removeAttribute('hidden')"
          {% if not documents %}disabled title="Нет документов"{% endif %}>
    <i data-lucide="lock-keyhole"></i> Запечатать
  </button>
```

Replace with:

```html
  {% set missing_settings = not operator_row or not operator_row.default_signer_sender_id or not operator_row.default_branch_id %}
  <button class="btn btn-primary"
          onclick="document.getElementById('seal-modal').removeAttribute('hidden')"
          {% if not documents %}disabled title="Нет документов"
          {% elif missing_settings %}disabled title="Настройте филиал и подписанта в Настройках"
          {% endif %}>
    <i data-lucide="lock-keyhole"></i> Запечатать
  </button>
```

- [ ] Apply the edit above.

### Step 2.2 — Replace the seal modal form (around lines 161–211)

Find this entire block:

```html
<!-- Seal modal -->
{% if env_status == 'draft' %}
<div id="seal-modal" hidden>
<div class="modal-overlay" onclick="if(event.target===this)this.parentElement.setAttribute('hidden','')">
<div class="modal">
  <div class="modal-title">Запечатать конверт</div>
  <form hx-post="/ui/envelopes/{{ envelope.id }}/seal"
        hx-target="#envelope-card" hx-swap="outerHTML">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="form-row">
        <label>Отправитель (подписант)</label>
        <select name="signer_sender_id" class="form-control" required>
          <option value="">— выберите —</option>
          {% for s in signers %}
          <option value="{{ s.id }}">{{ s.last_name }} {{ s.first_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-row">
        <label>Получатель (подписант)</label>
        <select name="signer_receiver_id" class="form-control" required>
          <option value="">— выберите —</option>
          {% for s in signers %}
          <option value="{{ s.id }}">{{ s.last_name }} {{ s.first_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-row">
        <label>Филиал-отправитель</label>
        <select name="origin_branch_id" class="form-control" required>
          <option value="">— выберите —</option>
          {% for b in branches %}
          <option value="{{ b.id }}">{{ b.name }}</option>
          {% endfor %}
        </select>
      </div>
    </div>
    <div class="form-row">
      <label>Примечания</label>
      <textarea name="notes" class="form-control" placeholder="необязательно"></textarea>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn btn-ghost"
              onclick="document.getElementById('seal-modal').setAttribute('hidden','')">Отмена</button>
      <button type="submit" class="btn btn-primary">Запечатать</button>
    </div>
  </form>
</div>
</div>
</div>
{% endif %}
```

Replace with:

```html
<!-- Seal modal -->
{% if env_status == 'draft' %}
<div id="seal-modal" hidden>
<div class="modal-overlay" onclick="if(event.target===this)this.parentElement.setAttribute('hidden','')">
<div class="modal">
  <div class="modal-title">Запечатать конверт</div>
  <form hx-post="/ui/envelopes/{{ envelope.id }}/seal"
        hx-target="#envelope-card" hx-swap="outerHTML">
    <input type="hidden" name="signer_sender_id" value="{{ operator_row.default_signer_sender_id }}">
    <input type="hidden" name="origin_branch_id" value="{{ operator_row.default_branch_id }}">
    <div class="form-row">
      <label>Подписант № 2 (экспедитор)</label>
      <select name="signer_receiver_id" class="form-control" required>
        <option value="">— выберите —</option>
        {% for s in signers %}
        <option value="{{ s.id }}">{{ s.last_name }} {{ s.first_name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-row">
      <label>Примечания</label>
      <textarea name="notes" class="form-control" placeholder="необязательно"></textarea>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn btn-ghost"
              onclick="document.getElementById('seal-modal').setAttribute('hidden','')">Отмена</button>
      <button type="submit" class="btn btn-primary">Запечатать</button>
    </div>
  </form>
</div>
</div>
</div>
{% endif %}
```

- [ ] Apply the edit above.

### Step 2.3 — Test: operator with settings configured

Prerequisites: your operator account has "Подписант отправителя" and "Филиал отправки" set in Настройки (gear icon, top right).

1. Create a new draft envelope and scan at least one document.
2. The "Запечатать" button must be **enabled** (not greyed out).
3. Click "Запечатать" — the modal opens showing only the "Подписант № 2 (экспедитор)" dropdown and a Notes field.
4. Select a signer, click "Запечатать".
5. The envelope should seal successfully and the card should update to `sealed` status.

- [ ] End-to-end seal works.

### Step 2.4 — Test: operator without settings

1. Go to Настройки, clear "Подписант отправителя" or "Филиал отправки", save.
2. Open a draft envelope with at least one document.
3. The "Запечатать" button must be **disabled** (greyed out).
4. Hover the button — tooltip shows "Настройте филиал и подписанта в Настройках".
5. Restore settings afterwards.

- [ ] Disabled state and tooltip verified.

### Step 2.5 — Commit

```bash
git add app/web/templates/partials/envelope_card.html
git commit -m "feat: seal modal now asks only for signer 2, uses operator settings for signer 1 and branch"
```

- [ ] Commit done.

---

## Task 3: Android TSD — signer picker before seal

**Files:**
- Modify: `android/app/src/main/java/ru/technoavia/konverttrack/MainActivity.kt:1568–1617`

### Step 3.1 — Locate the state block in `RegisterScreen`

Open `MainActivity.kt`. Find `RegisterScreen` at line ~1552. The state variables begin at ~line 1568:

```kotlin
var sealMessage by remember { mutableStateOf<String?>(null) }
var sealError by remember { mutableStateOf<String?>(null) }
var isSealing by remember { mutableStateOf(false) }
var printMessage by remember { mutableStateOf<String?>(null) }
var printError by remember { mutableStateOf<String?>(null) }
val scope = rememberCoroutineScope()
val context = LocalContext.current
val canSeal = envelope.documents.isNotEmpty() && branchId.isNotBlank() && signerId.isNotBlank()
val sealAction: () -> Unit = {
    if (!canSeal) {
        sealError = if (envelope.documents.isEmpty()) {
            "Добавьте хотя бы один документ"
        } else {
            "Выберите филиал и подписанта в сервисном меню"
        }
    } else {
        scope.launch {
            isSealing = true
            sealError = null
            sealMessage = null
            runCatching {
                ApiClient.envelopeApi(serverUrl).sealEnvelope(
                    envelope.id,
                    SealRequest(
                        signer_sender_id = signerId,
                        signer_receiver_id = signerId,
                        origin_branch_id = branchId,
                    ),
                )
            }.onSuccess { sealed ->
                onEnvelopeChanged(sealed)
                sealMessage = "Конверт запечатан"
            }.onFailure { err ->
                sealError = apiErrorText(err)
            }
            isSealing = false
        }
    }
}
```

### Step 3.2 — Replace that entire block

Replace everything from `var sealMessage` through the closing `}` of `sealAction` with:

```kotlin
var sealMessage by remember { mutableStateOf<String?>(null) }
var sealError by remember { mutableStateOf<String?>(null) }
var isSealing by remember { mutableStateOf(false) }
var printMessage by remember { mutableStateOf<String?>(null) }
var printError by remember { mutableStateOf<String?>(null) }
var showSealSignerSheet by remember { mutableStateOf(false) }
var sealSignersList by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
val scope = rememberCoroutineScope()
val context = LocalContext.current

LaunchedEffect(serverUrl) {
    runCatching {
        ApiClient.settingsApi(serverUrl).signers()
            .map { SelectOption(it.id, "${it.last_name} ${it.first_name}") }
    }.onSuccess { sealSignersList = it }
}

val canSeal = envelope.documents.isNotEmpty() && branchId.isNotBlank() && signerId.isNotBlank()

val doSeal: (String) -> Unit = { signer2Id ->
    scope.launch {
        isSealing = true
        sealError = null
        sealMessage = null
        runCatching {
            ApiClient.envelopeApi(serverUrl).sealEnvelope(
                envelope.id,
                SealRequest(
                    signer_sender_id = signerId,
                    signer_receiver_id = signer2Id,
                    origin_branch_id = branchId,
                ),
            )
        }.onSuccess { sealed ->
            onEnvelopeChanged(sealed)
            sealMessage = "Конверт запечатан"
        }.onFailure { err ->
            sealError = apiErrorText(err)
        }
        isSealing = false
    }
}

val sealAction: () -> Unit = {
    if (!canSeal) {
        sealError = if (envelope.documents.isEmpty()) {
            "Добавьте хотя бы один документ"
        } else {
            "Выберите филиал и подписанта в сервисном меню"
        }
    } else {
        showSealSignerSheet = true
    }
}
```

- [ ] Apply the edit above.

### Step 3.3 — Add `SelectionSheet` to the composable body

`ModalBottomSheet` must be a direct child of the composable, not nested inside a `Box` or `Surface` — this matches the existing pattern in `SettingsScreen` (lines ~2308–2333).

Find the closing `}` of `Box(modifier = Modifier.fillMaxSize())` in `RegisterScreen` (around line 1620). Place the block **after** that `}`, but still inside `RegisterScreen`'s function body:

```kotlin
if (showSealSignerSheet) {
    SelectionSheet(
        title = "Подписант № 2 (экспедитор)",
        options = sealSignersList,
        selectedId = "",
        onSelect = { selected ->
            showSealSignerSheet = false
            doSeal(selected.id)
        },
        onDismiss = { showSealSignerSheet = false },
    )
}
```

`SelectionSheet` is defined at line ~2531 in the same file. `SelectOption` is defined at line ~2408. Both are already in scope — no imports needed.

- [ ] Apply the edit above.

### Step 3.4 — Build and verify no compile errors

In Android Studio: **Build → Make Project** (or `Ctrl+F9`).

Expected: BUILD SUCCESSFUL, 0 errors.

- [ ] Build passes.

### Step 3.5 — Test on device

Device is already connected with USB debugging enabled.

Run in Android Studio (**Run → Run 'app'**) or via CLI:
```bash
cd E:/technodt/android
./gradlew installDebug
```

Test checklist:
1. Open a draft envelope on TSD with at least one document scanned.
2. Press **F1** (or the seal hardware button).
3. A bottom sheet titled **"Подписант № 2 (экспедитор)"** appears with the list of signers.
4. Tap a signer — sheet closes, envelope seals, banner shows "Конверт запечатан".
5. Press F1 again on an already-sealed envelope — nothing happens (bindSealEnvelope is null for sealed status).
6. Test with empty documents: press F1 — error banner "Добавьте хотя бы один документ", no sheet.

- [ ] All checklist items pass.

### Step 3.6 — Commit

```bash
git add android/app/src/main/java/ru/technoavia/konverttrack/MainActivity.kt
git commit -m "feat: TSD seal now prompts for signer 2 via picker sheet, fixes signer_receiver_id bug"
```

- [ ] Commit done.

---

## Done

All three tasks complete. The seal flow now:
- **Web:** one dropdown (подписант №2) + hidden signer1/branch from settings; button disabled with tooltip if settings incomplete
- **TSD:** F1 opens `SelectionSheet` with signer list; seals with correct `signer_receiver_id`
- **Bug fixed:** `signer_receiver_id` no longer duplicates `signer_sender_id` on TSD
