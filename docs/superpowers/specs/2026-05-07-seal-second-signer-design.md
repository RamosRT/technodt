# Seal Envelope: Second Signatory (Экспедитор)

**Date:** 2026-05-07  
**Status:** Approved

## Problem

When sealing an envelope, the operator must specify two signatories:
- **Signer 1** (отправитель) — already saved in operator settings (`default_signer_sender_id`)
- **Signer 2** (экспедитор) — selected at seal time; currently missing from TSD and duplicated from signer 1 by mistake

Currently:
- Web UI seal modal shows three full dropdowns (signer sender, signer receiver, branch) — redundant with settings
- Android TSD sends `signer_receiver_id = signerId` (same as sender) — a bug

## Goal

- Web and TSD: at seal time, ask only for **Signer 2 (экспедитор)** via a dropdown/picker
- Signer 1 and branch are taken silently from operator settings
- If operator settings are incomplete (no default signer or branch), disable the seal action with a clear hint

## Data Model

No changes. Existing fields are used as follows:

| Field | Source |
|---|---|
| `signer_sender_id` | `operator.default_signer_sender_id` (from settings) |
| `signer_receiver_id` | Selected at seal time — подписант №2 (экспедитор) |
| `origin_branch_id` | `operator.default_branch_id` (from settings) |

## Approach: Template-level defaults (Approach 1)

Operator defaults are resolved at the server level when rendering the envelope card template. No new API endpoints or client-side fetch calls.

---

## Backend Changes (`app/routers/ui/pages.py`)

### `_envelope_card_context` (line 274)

Add `operator_row` loading:

```python
operator_row = None
if operator:
    operator_row = (await session.execute(
        select(Operator).where(Operator.username == operator)
    )).scalar_one_or_none()
```

Add `"operator_row": operator_row` to the returned context dict.

**No changes** to `ui_seal_envelope` route — it continues to receive `signer_sender_id`, `signer_receiver_id`, `origin_branch_id` as `Form(...)` fields. The first two now arrive as hidden inputs instead of visible dropdowns.

---

## Web UI Changes (`app/web/templates/partials/envelope_card.html`)

### Seal button (line ~65)

Add a second disabled condition alongside `{% if not documents %}`:

```html
{% set missing_settings = not operator_row or not operator_row.default_signer_sender_id or not operator_row.default_branch_id %}
<button class="btn btn-primary"
        onclick="document.getElementById('seal-modal').removeAttribute('hidden')"
        {% if not documents or missing_settings %}disabled{% endif %}
        {% if missing_settings %}title="Настройте филиал и подписанта в Настройках"{% endif %}>
  <i data-lucide="lock-keyhole"></i> Запечатать
</button>
```

### Seal modal form (lines ~162–211)

Remove the two-column grid with signer sender and branch dropdowns. Replace with:

1. Two hidden inputs:
   ```html
   <input type="hidden" name="signer_sender_id" value="{{ operator_row.default_signer_sender_id }}">
   <input type="hidden" name="origin_branch_id" value="{{ operator_row.default_branch_id }}">
   ```

2. Single dropdown for signer 2:
   ```html
   <div class="form-row">
     <label>Подписант № 2 (экспедитор)</label>
     <select name="signer_receiver_id" class="form-control" required>
       <option value="">— выберите —</option>
       {% for s in signers %}
       <option value="{{ s.id }}">{{ s.last_name }} {{ s.first_name }}</option>
       {% endfor %}
     </select>
   </div>
   ```

3. Notes textarea stays as-is.

---

## Android TSD Changes (`android/app/src/main/java/.../MainActivity.kt`)

### `RegisterScreen` composable (line ~1552)

**New state variables:**
```kotlin
var showSealSignerSheet by remember { mutableStateOf(false) }
var sealSignersList by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
```

**Eager signers load** — add a `LaunchedEffect(serverUrl)` to load `/api/signers` when the screen mounts, so the sheet opens instantly when F1 is pressed:
```kotlin
LaunchedEffect(serverUrl) {
    runCatching {
        ApiClient.settingsApi(serverUrl).signers()
            .map { SelectOption(it.id, "${it.last_name} ${it.first_name}") }
    }.onSuccess { sealSignersList = it }
}
```

**`sealAction` change** — instead of calling `sealEnvelope` directly, open the picker:
```kotlin
val sealAction: () -> Unit = {
    if (!canSeal) {
        sealError = "Выберите филиал и подписанта в сервисном меню"
    } else {
        showSealSignerSheet = true
    }
}
```

**Actual seal logic** — extracted into a new `doSeal(signer2Id: String)` lambda called from `SelectionSheet.onSelect`:
```kotlin
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
```

**`SelectionSheet` in the composable body:**
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

---

## Edge Cases

| Situation | Behavior |
|---|---|
| Operator has no `default_signer_sender_id` or `default_branch_id` | Web: «Запечатать» button is disabled with tooltip. TSD: `canSeal = false`, existing error message shown. |
| `/api/signers` returns empty list on TSD | Sheet opens but empty — operator sees no options; seal is blocked until dismissed. |
| Signers load fails on TSD | `sealSignersList` stays empty; sheet opens empty. No crash. |
| Operator dismisses sheet without selecting | `showSealSignerSheet = false`, no seal action. |
