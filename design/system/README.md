# Handoff: Konvert-Trek (ТехноКонверт) — TSD Android UI

## Overview

**Konvert-Trek** (РУ: «Конверт-трек», UX-имя «ТехноКонверт») — внутренняя система учёта бухгалтерских документов, физически передаваемых между филиалами через курьеров в конвертах. Каждый конверт содержит документы (УПД, УКД, акты, счёт-фактуры), штрихкодируется (Code128, номер вида `ТА-NNNNNNNNNNNNNNNN`), запечатывается у отправителя и сверяется при получении.

Этот хэндофф покрывает **TSD-клиент** (Терминал сбора данных, handheld-сканер на Android — Urovo / Zebra, ~5–6 дюймов, портретный режим). Web-приложение оператора уже существует в `app/web/` и служит источником правды для токенов и логики.

Целевой стек TSD: **Kotlin + Jetpack Compose**, Material 3 (тёмные акценты, плотные списки). DataWedge / Intent для сканера, ZPL-печать по сети.

## About the Design Files

Файлы в этом пакете — **дизайн-референсы**, сделанные в HTML/JSX. Это интерактивный прототип, показывающий целевой вид и поведение, **не production-код для копирования**. Задача — **воспроизвести эти экраны в Compose** (или в существующем native-окружении проекта), используя его стандартные паттерны и библиотеки. Токены (цвета, типографика, отступы) переносите как `Color`/`Dp`/`TextStyle` в `theme/`.

## Fidelity

**High-fidelity.** Цвета, типографика, отступы, состояния — финальные, привязаны к Технониколь / Техноавиа brandbook и существующему web-стайлгайду. Воспроизводите попиксельно, используя `MaterialTheme` Compose или эквивалент.

## Screens / Views

Все экраны рассчитаны на портретный 360 dp viewport, sysbar 22 dp + AppBar 56 dp вверху, нижняя CTA-полоса 56 dp + safe-area, прокручиваемое тело между ними.

### 1. Login (`LoginScreen` в `ui_kits/tsd_android/components.jsx`)
- **Назначение:** ввод имени оператора + пароля, привязка к устройству.
- **Layout:**
  - 32 dp top padding, 22 dp horizontal.
  - Лого-локап (PNG) 220×~84 dp по центру + tagline `Учёт передачи документов · ТСД` (12 px, `--fg-3`).
  - Два инпута 44 dp высотой, label `UPPERCASE 10px .5px` letter-spacing.
  - CTA `Войти`: `t-btn-primary t-btn-cta` 56 dp, заполняющий ширину родителя (НЕ растянутый flex — `width: 100%`).
  - `device-strip` карточка: иконка `smartphone`, надпись `Устройство:` + bold `Urovo DT40 · DataWedge`.
  - Versionтекст внизу `v1.2.0 · build 184`, `Roboto Mono 10 px`, `--fg-4`.
- **Лого:** `assets/logo-lockup.png` (тёмно-синяя капсула с белым конвертом и шрифтовым знаком «ТехноКонверт»). Source: предоставленный заказчиком скриншот; в Compose положить как `painterResource(R.drawable.logo_lockup)`.

### 2. Home (`HomeScreen`)
- **Назначение:** главный экран после входа — точка входа в два сценария + история последних конвертов.
- **Layout:** AppBar (`ТехноКонверт` + subtitle = имя оператора, action right = `settings-2`). Connection banner (зелёный «Сеть · 1С · Принтер готовы»). Section «Действия» — две тайлы 1:1 grid (`Новый конверт` иконка `package-plus` синий, `Проверить` иконка `scan-line` зелёный alt). Section «Последние» — список карточек с leading-иконкой по статусу (warning / success / danger), title = номер конверта, sub = pill + кол-во док. + relative time.

### 3. Register (`RegisterScreen`)
- **Назначение:** создание нового конверта, сканирование документов, запечатывание, печать ZPL.
- **States:**
  - **Draft:** envelope hero (синий градиент), список добавленных документов (compact `t-doc-row` с кнопкой `x` для удаления), scan target armed (анимация пульса), bottom CTA `Запечатать` (primary) + close (ghost).
  - **Sealed:** hero меняется на `sealed` pill, документы становятся read-only, секция «Печать» (тональная кнопка ZPL-этикетки + ghost «Опись»), bottom CTA `Готово` (success).
- **Bottom sheet «Запечатать»:** селекторы подписант-отправитель, подписант-получатель, филиал-отправитель + Отмена/Запечатать.

### 4. Verify (`VerifyScreen`)
- **Назначение:** сверка содержимого конверта на принимающей стороне.
- **Layout:** hero показывает `scannedCount/docCount`, scan target до тех пор, пока `scanned.length < allDocs.length`. Список документов — все строки видны, отсканированные с зелёной подсветкой (`bg: var(--success-bg)`) и `check-circle-2`, ожидающие — серые с `circle`. Bottom CTA: `Завершить сверку` (success) когда всё сошлось, иначе `С расхождением` (danger) + close.
- **Toast:** `success`-зелёный при добавлении; `danger`-красный при сканировании постороннего ШК.

### 5. Service (`ServiceScreen`)
- **Назначение:** настройки оператора и устройства.
- **Sections:** Учётная запись (Оператор + Выйти), Предпочтения отправки (филиал, подписант — открывают bottom sheet с list-радио), Печать (термопринтер ZPL → переход в `PrinterScreen`), Об устройстве (ТСД model + serial, версия билда).
- Ряды строятся через `ServiceRow`: leading lucide 20 px серый, body { ttl 14/500, val 12/400 серый }, trailing chevron.

### 6. Printer (`PrinterScreen`)
- **Назначение:** выбор сетевого принтера ZPL + параметры этикетки.
- **Layout:** `t-printer-row` карточки (selected = blue border + tinted bg + 3 px ring + чек-иконка). Параметры: размер этикетки (58×40 / 100×50), копий, тестовая печать (тональная кнопка). Bottom CTA `Сохранить`.

## Interactions & Behavior

- **Сканер:** в реальном устройстве — broadcast от DataWedge, в прототипе — кнопка `scan-line` в AppBar или клавиша-trigger на frame. Каждый успешный скан: добавить документ → вибро-фидбэк (50 ms) → `Toast { kind: success }` 2.4 s.
- **Неверный ШК (verify):** красный toast «Документ не из этого конверта», звук error; список не меняется.
- **Анимации:**
  - `scan-pulse` на scan target — 1.6 s ease-in-out, рамка glows голубым.
  - `toast-in` 250 ms slide-up + fade.
  - `sheet-in` 250 ms translateY 100% → 0.
  - `fade-in` overlay 150 ms.
  - **Без bouncy spring**, без параллакса. Цель — подтверждение действия, не «delight».
- **Hover/press:** `:active { filter: brightness(.92); transform: scale(.98); }` на кнопках. На рядах списка — `background: var(--surface-alt)`.
- **Focus:** инпут `border: var(--brand-blue)` + `box-shadow 0 0 0 3px rgba(29,113,184,.15)`. Видим всегда — оператор работает аппаратной клавиатурой ТСД.
- **Disabled:** `opacity .4; cursor not-allowed`.
- **Bottom sheet:** swipe-down to close + tap-overlay-to-close.
- **Empty states:** иконка 56 dp в скруглённой плашке, заголовок 14/700, описание 12/400.

## State Management

Минимальный набор состояний (для Compose — `ViewModel + StateFlow`):

```
LoginScreen:        operator: String?, password: String
HomeScreen:         recentEnvelopes: List<EnvelopeSummary>
RegisterScreen:     envelope { number, status, docs[] }, sealed: Boolean, sheetOpen: Boolean, toast
VerifyScreen:       envelope, scannedIds: Set<DocId>, done: Boolean, toast
ServiceScreen:      operator, branch, sender (persisted prefs)
PrinterScreen:      printers[], selectedId, labelSize, copies
```

Сетевой слой (см. `app/api.py` в codebase): REST endpoints `/api/envelopes`, `/api/envelopes/{id}/seal`, `/api/envelopes/{id}/verify`. Авторизация — basic operator name (см. `app/auth.py`).

## Design Tokens

Все токены — в `colors_and_type.css`. Перенесите как Compose `Color()` и `dp/sp` в `ui/theme/`.

### Colors (RGB из брендбука)
| Token | Hex | Pantone / brandbook | Use |
|---|---|---|---|
| `--brand-ink` | `#1b2848` | PANTONE 2768 C / Чернильный 050 G | Primary text, dark CTA, AppBar fallback |
| `--brand-blue` | `#1d71b8` | PANTONE 285 C / Синий 050 G | Primary action, links, focus accent |
| `--brand-blue-mid` | `#00397a` | mid-stop | Gradient mid stop |
| `--brand-blue-light` | `#6ea9dc` | Светло-голубой 056 G | Soft tints, hover bottom-borders |
| `--brand-red` | `#cc0c00` | Алый 031 G | Destructive, discrepancy, admin badge |
| `--brand-red-alt` | `#e4032e` | PANTONE 485 C | Accent red |
| `--brand-green` | `#a5c715` | RAL 6039-aligned | Verified / scan-success |
| `--success` | `#2e7d32` | — | UI success states |
| `--warning` | `#b27b00` | — | UI warning states |
| `--danger` | `#cc0c00` | = brand-red | UI danger states |
| Neutrals 8-step | `#f0f4f8 → #1b2848` | — | bg → fg-1 ramp |

**Gradient rule (брендбук):** только углы 45°–115°. **Никогда 90°.** Три именованных градиента в CSS: `--grad-blue`, `--grad-red`, `--grad-warning` — все 105°.

### Typography
- **Roboto** 300 / 400 / 500 / 700 — основная.
- **Roboto Condensed** 400 / 700 — заголовки, шапки таблиц, бейджи, цифровые/штрихкодные токены (выступает де-факто моноширинной).
- Шкала: 11 / 12 / 13 / 14 / 16 / 18 / 22 / 28 / 36. Body — 13–14, headings — 16–22.
- **TSD-CTA ≥ 16 px, hit-area ≥ 44 dp.**
- Casing: Sentence case у кнопок; `UPPERCASE + .5px letter-spacing` у eyebrow / labels.

### Spacing
4-px база. Шаги: 4 / 8 / 12 / 16 / 20 / 24.

### Radii
4 / 6 / 8 / 10 / 999. **6 dp default** для кнопок/инпутов, **8 dp** для карточек/чипов, **10 dp** для модалок, **999** для пиллов.

### Shadows
Четырёхступенчатая лесенка `--shadow-sm/md/lg/xl`, все тонированы `rgba(27,40,72, …)` — глубина читается как чернила, не чёрный.

### Hit areas
- `--hit-cta: 56dp` (primary CTA внизу).
- `--hit-min: 44dp` (вторичные действия, ряды списка).

## Assets

| Asset | Origin | Use |
|---|---|---|
| `assets/logo-lockup.png` | Извлечён из скриншота, предоставленного заказчиком | Login screen, splash |
| `assets/logo-icon.png` | `app/web/static/icon.png` в codebase | AppBar logo / system icon (32×32) |
| `assets/bird.svg` | `app/web/static/bird_extracted.svg` | Secondary brand mark, резерв |
| `fonts/Roboto-*.ttf` | Google Fonts (Apache 2.0) | Self-hosted шрифт |
| `fonts/RobotoCondensed-*.ttf` | Google Fonts (Apache 2.0) | Self-hosted шрифт |

**Иконки:** [Lucide](https://lucide.dev) — в HTML-прототипе через CDN. Для Android используйте **Lucide Android port** (`com.composables:lucide-icons-compose`) или экспортируйте нужные SVG в `res/drawable/`. Список используемых иконок:

`package-plus`, `scan-line`, `book-open`, `archive`, `file-text`, `circle-user`, `settings-2`, `log-out`, `lock-open`, `unlock`, `triangle-alert`, `info`, `history`, `user`, `clock`, `users`, `user-plus`, `trash-2`, `check`, `x`, `chevron-down`, `chevron-right`, `chevron-left`, `arrow-left`, `printer`, `printer-check`, `wifi`, `wifi-low`, `wifi-off`, `qr-code`, `package`, `package-check`, `package-x`, `package-open`, `layout-grid`, `log-in`, `smartphone`, `building-2`, `user-round`, `circle`, `circle-x`, `check-circle-2`, `rotate-cw`.

**Без эмодзи. Без юникод-символов как иконок.**

## Files in this bundle

| Path | Purpose |
|---|---|
| `SYSTEM_README.md` | Полный design system index — content rules, тоны, словарь, состояния. **Прочесть первым.** |
| `SKILL.md` | Skill-манифест для Claude Code. Положите в `.claude/skills/technokonvert-design/SKILL.md`. |
| `colors_and_type.css` | Все CSS токены. Источник правды для `Color`/`TextStyle`/`Dp` в Compose. |
| `fonts/` | Roboto + Roboto Condensed (TTF). |
| `assets/` | Лого PNG, bird SVG. |
| `ui_kits/tsd_android/index.html` | Запускаемый прототип (open в браузере). |
| `ui_kits/tsd_android/styles.css` | TSD-специфичные стили (поверх `colors_and_type.css`). |
| `ui_kits/tsd_android/components.jsx` | Реакт-компоненты: `StatusBar`, `AppBar`, `ConnBanner`, `StatusPill`, `EnvelopeHero`, `ScanTarget`, `DocRow`, `Tile`, `Toast`, `ServiceRow`, `Empty`, `BottomSheet`, `LoginScreen`. |
| `ui_kits/tsd_android/screens.jsx` | Экраны: `HomeScreen`, `RegisterScreen`, `VerifyScreen`, `ServiceScreen`, `PrinterScreen`. |

## Где это положить в репозитории `RamosRT/technodt`

```
design/
  system/                     ← скопировать содержимое этого пакета сюда
    SYSTEM_README.md
    SKILL.md
    colors_and_type.css
    fonts/
    assets/
    ui_kits/tsd_android/
.claude/
  skills/
    technokonvert-design/
      SKILL.md                ← скопировать SKILL.md ещё и сюда, чтобы Claude Code видел skill
```

После этого в любой Claude Code сессии в этом репо можно говорить «следуй technokonvert-design» — агент прочитает `SKILL.md` и подтянет остальное.

## Translation contract: CSS → Compose

Создайте `ui/theme/Color.kt`, `Type.kt`, `Theme.kt`. Маппинг:

```kotlin
// Color.kt
val BrandInk         = Color(0xFF1B2848)
val BrandBlue        = Color(0xFF1D71B8)
val BrandBlueMid     = Color(0xFF00397A)
val BrandBlueLight   = Color(0xFF6EA9DC)
val BrandRed         = Color(0xFFCC0C00)
val BrandGreen       = Color(0xFFA5C715)
val SurfaceTint      = Color(0xFFE6F0F8)
val Border           = Color(0xFFDDE4EF)
// ...

val GradBlue = Brush.linearGradient(
    colors = listOf(BrandBlueMid, BrandBlue, BrandBlueLight),
    start = Offset(0f, 0f),
    end = Offset(1f, 0.27f)  // 105° в декартовой
)

// Type.kt — Roboto + Roboto Condensed заведите как FontFamily,
// положите TTF в res/font/, дайте им Compose-aliases.
```

CTA-кнопка должна быть `Modifier.height(56.dp).fillMaxWidth()`, фон = `GradBlue` или solid `BrandBlue`. Bottom-bar через `Scaffold(bottomBar = { ... })`.

---

**Если что-то непонятно** — открой `ui_kits/tsd_android/index.html` в браузере и нажимай по навигации слева, это самый быстрый способ понять флоу.
