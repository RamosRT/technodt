# ТехноКонверт v1.2 Android TSD Implementation Plan

> **For agentic workers:** execute task-by-task and update checkboxes as work lands. Keep UI text Russian, code identifiers English. Use `design/system/` as the visual source of truth and `docs/superpowers/specs/2026-05-04-android-tsd-design.md` as the product source of truth.

**Goal:** Add a native Android TSD client for registration, sealing, printing, and verification of envelopes. Prepare the FastAPI backend with mobile-friendly auth/session and printer endpoints, then scaffold and implement the Kotlin + Jetpack Compose app in `android/`.

**Architecture:** Android is a sibling project inside the same repo. The backend remains the source of truth for envelope state, OData lookups, audit, and printing. The Android app is online-only for v1.2; it keeps only operator/session, server URL, preferred branch/signer, and selected printer in DataStore. Scanner input arrives through vendor Broadcast Intents and is normalized into one `Flow<String>`.

**Tech Stack:** Kotlin, Jetpack Compose, Material 3, Hilt, Retrofit 2, OkHttp CookieJar, Coroutines + StateFlow, DataStore Preferences, SoundPool, minSdk 26, targetSdk 34.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `docs/superpowers/specs/2026-05-04-android-tsd-design.md` | Reference | Product and UI spec |
| `app/routers/api/auth.py` | **Create** | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| `app/routers/api/printers.py` | **Create** | Printer discovery and backend-side print-send endpoints |
| `app/services/printers.py` | **Create** | Printer config parsing and TCP ZPL sender |
| `app/schemas/auth.py` | **Create** | Auth request/response DTOs |
| `app/schemas/printer.py` | **Create** | Printer DTOs |
| `app/config.py` | Modify | Cookie max-age and configured printer list |
| `app/main.py` | Modify | Register auth/printer routers |
| `tests/test_api_auth.py` | **Create** | Mobile auth/session tests |
| `tests/test_api_printers.py` | **Create** | Printer list/send behavior tests |
| `android/settings.gradle.kts` | **Create** | Android Gradle project settings |
| `android/build.gradle.kts` | **Create** | Root Gradle plugin versions |
| `android/app/build.gradle.kts` | **Create** | App dependencies and Android config |
| `android/app/src/main/AndroidManifest.xml` | **Create** | MainActivity, scanner receiver permissions if needed |
| `android/app/src/main/java/ru/technoavia/konverttrack/` | **Create** | Kotlin app code |
| `android/app/src/main/res/font/` | **Create** | Roboto and Roboto Condensed copied from `design/system/fonts/` |
| `android/app/src/main/res/drawable/` | **Create** | Logo assets and exported Lucide icons |
| `android/app/src/main/res/raw/` | **Create** | Scan success/error sounds |

---

## API Contract Snapshot

Existing backend endpoints used by Android:

| Endpoint | Use |
|---|---|
| `POST /api/envelopes` | Create draft envelope |
| `GET /api/envelopes?status=...&page=1&page_size=10` | Recent envelopes on Home |
| `GET /api/envelopes/by-barcode/{barcode}` | Start verification by envelope barcode |
| `GET /api/envelopes/{id}` | Refresh envelope detail |
| `POST /api/envelopes/{id}/documents` | Add scanned document |
| `DELETE /api/envelopes/{id}/documents/{doc_id}` | Remove document while draft |
| `POST /api/envelopes/{id}/seal` | Seal envelope |
| `POST /api/envelopes/{id}/verify/start` | Start receiving verification |
| `POST /api/envelopes/{id}/verify/scan` | Mark document as scanned |
| `POST /api/envelopes/{id}/verify/finish` | Finish verification |
| `GET /api/branches` | Branch selector |
| `GET /api/signers` | Signer selector |

New v1.2 backend endpoints:

| Endpoint | Use |
|---|---|
| `POST /api/auth/login` | Set `operator_name` cookie for Android |
| `GET /api/auth/me` | Validate stored session at launch and after 401 |
| `POST /api/auth/logout` | Clear `operator_name` cookie |
| `GET /api/printers` | Return configured printers |
| `POST /api/envelopes/{id}/print/label/send?printer_id=...` | Send ZPL label through backend |
| `POST /api/envelopes/{id}/print/inventory/send?printer_id=...` | Future A4 print handoff; can return 501 in first pass |

---

## Task 1: Backend Mobile Auth

**Files:**
- Create: `app/schemas/auth.py`
- Create: `app/routers/api/auth.py`
- Modify: `app/config.py`
- Modify: `app/main.py`
- Create: `tests/test_api_auth.py`

- [x] **Step 1: Add config for cookie lifetime**

Add to `Settings`:

```python
auth_cookie_max_age_seconds: int = 28800
```

- [x] **Step 2: Add auth schemas**

```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LoginResponse(BaseModel):
    ok: bool
    operator: str


class MeResponse(BaseModel):
    operator: str
    is_admin: bool
```

- [x] **Step 3: Implement `POST /api/auth/login`**

Behavior:
- Trim `name`.
- Call `ensure_operator(session, name, bootstrap=...)`.
- Reject inactive operator with 403.
- Set `operator_name` cookie with `httponly=True`, `samesite="lax"`, `max_age=settings.auth_cookie_max_age_seconds`.
- Return `{"ok": true, "operator": name}`.

- [x] **Step 4: Implement `GET /api/auth/me`**

Behavior:
- Require `operator_name` cookie.
- Decode and trim.
- Load/create operator through existing auth logic.
- Return `operator` and `is_admin`.
- Return 401/403 through existing `AppError` handling when missing/inactive.

- [x] **Step 5: Implement `POST /api/auth/logout`**

Behavior:
- Delete `operator_name` cookie.
- Return `204 No Content`.

- [x] **Step 6: Register router in `app/main.py`**

Import `app.routers.api.auth as auth_api` and include it before UI routers.

- [x] **Step 7: Add tests**

Cover:
- login sets cookie and returns operator.
- me returns operator for valid cookie.
- me returns 401 when cookie is missing.
- inactive operator cannot login.
- logout clears cookie.

Run:

```powershell
venv\Scripts\python -m pytest tests/test_api_auth.py -q
```

---

## Task 2: Backend Printer API

**Files:**
- Create: `app/schemas/printer.py`
- Create: `app/services/printers.py`
- Create: `app/routers/api/printers.py`
- Modify: `app/config.py`
- Modify: `app/main.py`
- Create: `tests/test_api_printers.py`

- [x] **Step 1: Add printer config**

Keep config simple for Windows Server deployment:

```python
printers_json: str = "[]"
```

Expected JSON:

```json
[
  {"id":"zpl-main","name":"Zebra склад","kind":"zpl","host":"192.168.1.50","port":9100,"dpi":200},
  {"id":"a4-office","name":"A4 бухгалтерия","kind":"a4","host":"","port":0,"dpi":0}
]
```

- [x] **Step 2: Add printer schemas**

```python
from pydantic import BaseModel, Field


class PrinterOut(BaseModel):
    id: str
    name: str
    kind: str
    host: str | None = None
    port: int | None = None
    dpi: int | None = None


class PrinterListResponse(BaseModel):
    items: list[PrinterOut]
```

- [x] **Step 3: Implement `services.printers`**

Functions:
- `list_printers(settings) -> list[PrinterOut]`
- `get_printer(settings, printer_id: str) -> PrinterOut`
- `send_zpl(printer: PrinterOut, payload: str, timeout: float = 5.0) -> None`

Rules:
- Validate JSON with Pydantic, raise 500 for malformed config.
- For ZPL, require `host` and `port`.
- Use `socket.create_connection((host, port), timeout=timeout)` and send UTF-8 bytes.

- [x] **Step 4: Add `GET /api/printers`**

Requires operator auth. Return configured printers.

- [x] **Step 5: Add label send endpoint**

`POST /api/envelopes/{id}/print/label/send?printer_id=...`

Behavior:
- Require operator auth.
- Load envelope.
- Render ZPL using existing `printing.render_label_zpl`.
- Send to selected `kind=zpl` printer.
- Return `204 No Content`.

- [x] **Step 6: Add inventory send endpoint**

`POST /api/envelopes/{id}/print/inventory/send?printer_id=...`

First pass may return `501 Not Implemented` for `kind=a4` with message `Печать описи с ТСД пока не настроена`. This keeps the API shape stable without pretending Windows A4 system printing is done.

- [x] **Step 7: Add tests**

Cover:
- printer list requires auth.
- list returns parsed config.
- unknown printer returns 404.
- label send calls mocked socket sender with generated ZPL.
- malformed printer config returns clear 500.

Run:

```powershell
venv\Scripts\python -m pytest tests/test_api_printers.py -q
```

---

## Task 3: Android Project Bootstrap

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/ru/technoavia/konverttrack/MainActivity.kt`
- Create: `android/app/src/main/java/ru/technoavia/konverttrack/ConvertTrackApp.kt`

- [x] **Step 1: Create Gradle project**

Use package `ru.technoavia.konverttrack`.

Recommended dependency set:
- `androidx.core:core-ktx`
- `androidx.activity:activity-compose`
- `androidx.compose.ui:ui`
- `androidx.compose.material3:material3`
- `androidx.navigation:navigation-compose`
- `androidx.lifecycle:lifecycle-runtime-compose`
- `com.google.dagger:hilt-android`
- `androidx.hilt:hilt-navigation-compose`
- `com.squareup.retrofit2:retrofit`
- `com.squareup.retrofit2:converter-gson`
- `com.squareup.okhttp3:logging-interceptor`
- `androidx.datastore:datastore-preferences`

- [x] **Step 2: Add app shell**

`MainActivity` should set content with `KonvertTrackTheme { AppNavHost() }`.

- [ ] **Step 3: Add Hilt app class**

`ConvertTrackApp : Application()` annotated with `@HiltAndroidApp`.

- [x] **Step 4: Verify project sync**

Run from `android/`:

```powershell
.\gradlew.bat :app:assembleDebug
```

If Gradle wrapper is not present, generate or add it with Android Studio on the dev machine.

---

## Task 4: Android Theme and Assets

**Files:**
- Create: `android/app/src/main/java/ru/technoavia/konverttrack/ui/theme/Color.kt`
- Create: `android/app/src/main/java/ru/technoavia/konverttrack/ui/theme/Type.kt`
- Create: `android/app/src/main/java/ru/technoavia/konverttrack/ui/theme/Theme.kt`
- Copy: `design/system/fonts/*.ttf` to `android/app/src/main/res/font/`
- Copy: `design/system/assets/logo-lockup.png` and `logo-icon.png` to `android/app/src/main/res/drawable/`

- [ ] **Step 1: Port color tokens**

Use exact tokens from `design/system/colors_and_type.css`:
- `BrandInk = Color(0xFF1B2848)`
- `BrandBlue = Color(0xFF1D71B8)`
- `BrandBlueMid = Color(0xFF00397A)`
- `BrandBlueLight = Color(0xFF6EA9DC)`
- `BrandRed = Color(0xFFCC0C00)`
- `BrandRedAlt = Color(0xFFE4032E)`
- `BrandGreen = Color(0xFFA5C715)`

Disable Android dynamic color for this internal brand app.

- [ ] **Step 2: Port typography**

Use Roboto for body and Roboto Condensed for titles, labels, envelope numbers, barcodes, and status pills.

- [ ] **Step 3: Add gradient helper**

Create reusable `Modifier.brandBlueBackground()` or `Brush.gradBlue` using the 105-degree rule from the design system. Do not use 90-degree gradients.

- [ ] **Step 4: Add previews**

Create light-theme previews for buttons, status pills, and document rows at 360 dp width.

---

## Task 5: Data and Network Layer

**Files:**
- Create: `data/api/ConvertTrackApi.kt`
- Create: `data/api/dto/*.kt`
- Create: `data/network/NetworkModule.kt`
- Create: `data/prefs/AppPreferences.kt`
- Create: `data/repository/EnvelopeRepository.kt`
- Create: `data/repository/DictionaryRepository.kt`
- Create: `data/repository/AuthRepository.kt`
- Create: `data/repository/PrinterRepository.kt`

- [x] **Step 1: Define Retrofit interface**

Mirror the API Contract Snapshot. Use suspend functions and DTO classes.

- [ ] **Step 2: Add persistent CookieJar**

Store `operator_name` cookie through OkHttp. DataStore keeps display operator name and server URL; the HTTP cookie store owns cookie expiry.

- [ ] **Step 3: Add 401 handling**

Use an OkHttp interceptor or repository-level wrapper:
- 401/403 clears auth cookie and emits `AuthExpired`.
- `IOException` maps to `NetworkUnavailable` and does not log out.

- [ ] **Step 4: Add repositories**

Repositories return `Result<T>` or a sealed `AppError` type. ViewModels must not parse HTTP error bodies directly.

- [ ] **Step 5: Unit-test DTO mapping**

Add JVM tests for envelope status mapping and error handling before wiring UI flows.

---

## Task 6: Scanner Layer

**Files:**
- Create: `data/scanner/ScannerManager.kt`
- Create: `data/scanner/UrovoScannerManager.kt`
- Create: `data/scanner/MindeoScannerManager.kt`
- Create: `data/scanner/ScannerModule.kt`

- [ ] **Step 1: Define common scanner interface**

```kotlin
interface ScannerManager {
    val barcodes: Flow<String>
    fun start(context: Context)
    fun stop(context: Context)
}
```

- [ ] **Step 2: Implement Urovo broadcast receiver**

Start with action `urovo.rcv.message`, extra `barcodeStr`. Keep action/extra constants in one file so they can be changed after device validation.

- [ ] **Step 3: Implement Mindeo placeholder**

Use the same broadcast pattern with constants marked `TODO(device validation)`. Do not block the rest of the app on exact Mindeo action names.

- [ ] **Step 4: Add scanner debug fallback**

For emulator/debug builds, expose a manual barcode input action on screens. Hide it behind `BuildConfig.DEBUG` so operators do not see it in release.

- [ ] **Step 5: Add scan feedback service**

Create `ScanFeedback` using `Vibrator` and `SoundPool`. Successful scan: 50 ms + `scan_success`. Error: three short pulses + `scan_error`.

---

## Task 7: Navigation and Session Startup

**Files:**
- Create: `ui/navigation/AppNavHost.kt`
- Create: `ui/session/SessionViewModel.kt`
- Create: `ui/login/LoginScreen.kt`
- Create: `ui/login/LoginViewModel.kt`

- [ ] **Step 1: Add app routes**

Routes:
- `login`
- `home`
- `register`
- `verify/{envelopeId}`
- `service`
- `printer`

- [ ] **Step 2: Startup session check**

At launch:
- If server URL missing: show Login with server URL field.
- If cookie exists: call `GET /api/auth/me`.
- 200 -> Home.
- 401 -> Login.
- IOException -> blocking server-unavailable state with `Повторить`.

- [x] **Step 3: Login screen**

Follow design system:
- Logo lockup centered.
- Operator name field.
- Server URL field only when missing or editing.
- Bottom CTA `Войти`, 56 dp.
- Device strip with manufacturer/model.

---

## Task 8: Home Screen

**Files:**
- Create: `ui/home/HomeScreen.kt`
- Create: `ui/home/HomeViewModel.kt`
- Create/extend: `ui/components/AppBar.kt`, `ConnBanner.kt`, `ActionTile.kt`, `RecentEnvelopeRow.kt`

- [ ] **Step 1: Load dashboard data**

On entry:
- `GET /api/auth/me`
- `GET /api/envelopes?page=1&page_size=10`
- `GET /api/printers`

Connection banner is green only when backend and printer list are reachable.

- [ ] **Step 2: Add action tiles**

Two 1:1 tiles:
- `Новый конверт`
- `Проверить`

- [ ] **Step 3: Add recent list**

Show number, status pill, document count, and created/sealed relative time.

- [ ] **Step 4: Wire navigation**

`Новый конверт` creates the draft immediately and navigates to Register with the returned ID. `Проверить` navigates to scan-envelope mode.

---

## Task 9: Register Screen

**Files:**
- Create: `ui/register/RegisterScreen.kt`
- Create: `ui/register/RegisterViewModel.kt`
- Create/extend components: `EnvelopeHero`, `DocRow`, `ScanTarget`, `BottomCta`, `SealSheet`, `ToastHost`

- [ ] **Step 1: Load draft envelope**

Fetch envelope by ID. If status is not `draft`, render read-only sealed state.

- [ ] **Step 2: Handle document scans**

For each barcode:
- Call `POST /api/envelopes/{id}/documents`.
- On success: refresh local docs from response/envelope detail, success feedback.
- On 409/422: show backend detail as red toast, error feedback.

- [ ] **Step 3: Remove document**

Row delete button calls `DELETE /api/envelopes/{id}/documents/{doc_id}`. Hide delete affordance once sealed.

- [ ] **Step 4: Seal sheet**

Load branches/signers, preselect DataStore defaults, require sender signer, receiver signer, origin branch. Call `POST /api/envelopes/{id}/seal`.

- [ ] **Step 5: Print after seal**

After successful seal:
- Call label send endpoint if selected printer exists.
- Show `Этикетка отправлена на принтер` or `Принтер не отвечает`.
- Do not roll back seal when printing fails.

---

## Task 10: Verify Flow

**Files:**
- Create: `ui/verify/VerifyScreen.kt`
- Create: `ui/verify/VerifyViewModel.kt`

- [ ] **Step 1: Scan envelope entry**

If route has no envelope ID, first scanned barcode is treated as envelope barcode:
- Call `GET /api/envelopes/by-barcode/{barcode}`.
- Require `sealed` status.
- Navigate to `verify/{id}`.

- [ ] **Step 2: Start verification**

Call `POST /api/envelopes/{id}/verify/start` when entering the detail flow.

- [ ] **Step 3: Handle document scans**

Call `POST /api/envelopes/{id}/verify/scan`.
- `matched=true`: mark row green with check icon.
- `matched=false`: red toast `Документ не из этого конверта`.

- [ ] **Step 4: Finish verification**

If all documents scanned: CTA `Завершить сверку`, call finish with `force=false`.
If missing documents remain: CTA `Завершить с расхождением`, show confirmation sheet, call finish with `force=true`.

- [ ] **Step 5: Post-finish screen**

Show final status and offer `Готово`. For discrepancy, keep a secondary action for discrepancy act only if backend printing endpoint is implemented.

---

## Task 11: Service and Printer Screens

**Files:**
- Create: `ui/service/ServiceScreen.kt`
- Create: `ui/service/ServiceViewModel.kt`
- Create: `ui/printer/PrinterScreen.kt`
- Create: `ui/printer/PrinterViewModel.kt`

- [ ] **Step 1: Service rows**

Rows:
- Operator and logout.
- Server URL.
- Preferred branch.
- Preferred sender.
- ZPL printer.
- Device model/serial.
- App version/build.

- [ ] **Step 2: Preference sheets**

Use bottom sheets with radio rows for branch, signer, and printer selection.

- [ ] **Step 3: Printer screen**

Load `GET /api/printers`, show selected printer with blue border and check icon. Persist `printerId`, label size, and copies.

- [ ] **Step 4: Test print**

If no backend test-print endpoint exists, hide test print in release and keep it debug-only until Task 2 adds a stable route.

---

## Task 12: QA and Device Validation

- [ ] **Backend tests**

```powershell
venv\Scripts\python -m pytest -q
```

- [ ] **Android static checks**

```powershell
cd android
.\gradlew.bat :app:ktlintCheck :app:testDebugUnitTest :app:assembleDebug
```

- [ ] **Emulator smoke test**

Validate:
- login with server URL.
- create envelope.
- debug scan adds document using a known test barcode.
- seal displays print error if no printer configured but keeps envelope sealed.
- verify envelope path handles successful and wrong barcode scans.

- [ ] **Urovo device test**

Validate:
- Broadcast action and extra names.
- Scanner trigger does not open keyboard.
- Cyrillic operator names survive cookie roundtrip.
- Vibration/sound latency is acceptable.
- Portrait 360 dp layout fits without overlap.

- [ ] **Mindeo device test**

Validate action/extra constants and update `MindeoScannerManager`.

---

## Task 13: Release Packaging

- [ ] Add release build type with minification disabled for first field trial.
- [ ] Configure app label `ТехноКонверт`.
- [ ] Configure launcher icon from `logo-icon.png`.
- [ ] Produce signed APK for pilot devices.
- [ ] Document server URL, DataWedge profile, printer config, and APK installation steps in `docs/android-tsd-operator-setup.md`.

---

## Open Decisions

- [ ] Confirm exact Urovo i6310 / DT40 broadcast action and extra names on real devices.
- [ ] Confirm Mindeo M40 scanner broadcast contract.
- [ ] Decide whether A4 inventory print from TSD is needed in v1.2 or can stay web-only.
- [ ] Decide whether Android should allow manual barcode entry in release for scanner-failure fallback.
- [ ] Decide printer config format in `.env`: JSON string vs separate DB table. For v1.2, JSON is faster and lower-risk.
