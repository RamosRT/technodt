# Konvert-Trek (ТехноКонверт) Design System

A design system for **Konvert-Trek** (Конверт-трек / "ТехноКонверт"), an internal accounting-document tracking system. The system manages physical envelopes that move accounting documents (УПД, УКД, акты, счёт-фактуры) between branches via couriers. Each document is scanned into a virtual envelope, sealed, and verified at the receiving end.

The visual identity is rooted in the **Технониколь / Техноавиа** corporate brandbook (RGB tokens, gradients 45°–115°, Roboto type, Pantone 2768 C ink + Pantone 285 C blue + Pantone 485 C red).

---

## Products in scope

This design system covers two surfaces:

1. **TSD (Android handheld scanner) app** — *primary focus of this system.*
   Native Kotlin + Jetpack Compose; scanner via DataWedge/Intent.
   Restricted feature set: auth, new envelope registration, existing envelope verification, ZPL printing to a chosen thermal printer, and a service menu (login/logout, preferred sender branch, preferred sender name).
2. **Web (PC operator) app** — *recreated from the existing codebase as reference.*
   FastAPI + HTMX + vanilla JS one-page application. Provides full envelope/document/admin/audit views.

The web codebase is the most authoritative source of brand expression in code today; this system lifts its tokens, colors, and component logic and adapts them for the Android/TSD form factor.

---

## Sources

- **Codebase:** `RamosRT/technodt` (GitHub, default branch `main`)
  - `app/web/static/style.css` — full corporate stylesheet (Roboto, brand tokens, navbar, cards, tables, audit, modals).
  - `app/web/templates/base.html`, `index.html`, `partials/*.html`, `print/*.html` — interface markup.
  - `app/web/static/icon.png` — app icon (used as logo glyph in navbar).
  - `app/web/static/bird_extracted.svg` — secondary brand mark.
- **Brandbook screenshots** (`design/Screenshot_4–6.png` in repo, copied into `assets/`):
  - Colors & gradients (Светло-голубой 056 G, Синий 050 G, Алый 031 G; rule "no 90° gradients").
  - Typography (Roboto + Roboto Condensed; Roboto Slab + TT Hoves mentioned but not used in code).
  - PANTONE / CMYK / RGB / ORACAL palette references.
- **Specs/plans:** `project-overview.md`, `docs/superpowers/plans/*.md`, `docs/superpowers/specs/*.md` — describe MVP, v1.1 list/audit features, and the Android client roadmap (v1.2).

The web codebase has been read and tokens/components have been lifted; nothing from the binaries has been re-rendered, only bundled.

---

## Index

| File / Folder | Purpose |
| --- | --- |
| `README.md` | This file. Brand context, content fundamentals, visual foundations, iconography. |
| `colors_and_type.css` | All design tokens (color, type, spacing, radii, shadows, gradients, motion). Drop-in. |
| `SKILL.md` | Agent skill manifest — makes this folder portable to Claude Code. |
| `fonts/` | Self-hosted Roboto + Roboto Condensed (TTF, official Google licence). |
| `assets/` | Logo, brand-mark bird, and three reference brandbook page bitmaps. |
| `preview/` | Standalone HTML cards that populate the Design System review tab. |
| `ui_kits/tsd_android/` | The handheld TSD UI kit — primary deliverable. Components + interactive index.html. |
| `ui_kits/web_operator/` | The PC web-app recreation — reference / parity surface. |

---

## Content Fundamentals

The product is **Russian-language, internal, operational**. Copy is for warehouse / accounting operators on a 5–6" handheld device or a PC with a barcode scanner.

- **Language:** Russian (ru-RU). All UI strings are Russian; document/branch names are mixed Cyrillic + Latin numbers/codes.
- **Tone:** Neutral-corporate, terse, instructional. No marketing voice. No emoji. No exclamation points. Sentence-case for body, **Sentence case** for buttons, **UPPERCASE small labels** with letter-spacing for `.eyebrow`/field labels.
- **Person:** Impersonal / imperative ("Сканируйте документ", "Введите имя оператора"). Never "you" / "вы" addresses; never first-person.
- **Domain vocabulary** (use exactly):
  - **Конверт** — envelope (the unit). Has a number (`ТА-NNNNNNNNNNNNNNNN`) and a Code128 barcode.
  - **Документ** — a single accounting document inside an envelope (УПД, УКД, акт, счёт-фактура).
  - **ШК** — штрихкод (barcode).
  - **Запечатать / Распечатать** — seal / unseal an envelope.
  - **Сверка / Верификация** — verification at receiving end.
  - **Подписант** — signer (sender or receiver).
  - **Филиал** — branch.
  - **ТСД** — Терминал сбора данных (the handheld scanner device).
- **Status labels** (always lower-case in body, capitalised in pills):
  Черновик · Запечатан · Сверен · С расхождением.
- **Timestamps** are always `dd.mm.yyyy HH:MM` (24-hour, dot-separated, no AM/PM).
- **Numbers, IDs, barcodes** are rendered in `Roboto Condensed` with `letter-spacing: .5px` (treat as monospace for alignment).
- **Concrete copy examples:**
  - Empty state: "Событий пока нет"
  - Empty list: "Документы не найдены"
  - Scan hint: "Сканируйте документы или ШК черновика конверта"
  - Discrepancy CTA: "Завершить с расхождением"
  - Confirmation copy: "Не все документы отсканированы. Вы уверены что желаете завершить проверку?"
  - Login: "Вход в систему" → "Введите ваше имя, чтобы продолжить"
- **Error messages** are factual and short: "ШК не похож на штрихкод документа 1С", "1С недоступна, попробуйте позже".
- **Microcopy density:** dense — operators are repeat users, screens are wide, no need for hand-holding.

---

## Visual Foundations

### Colors

| Token | Hex | Brandbook | Use |
| --- | --- | --- | --- |
| `--brand-ink` | `#1b2848` | PANTONE 2768 C / Чернильный 050 G | Primary text, app header, table headers, dark CTA |
| `--brand-blue` | `#1d71b8` | PANTONE 285 C / Синий 050 G end-stop | Primary action, links, focus accent |
| `--brand-blue-light` | `#6ea9dc` | Светло-голубой 056 G start-stop | Hover bottom-borders, soft tints |
| `--brand-red` | `#cc0c00` | Алый 031 G | Destructive, discrepancy, admin badge |
| `--brand-red-alt` | `#e4032e` | PANTONE 485 C | Accent red for badges |
| `--brand-green` | `#a5c715` | RAL 6039-aligned | Verified / scan-success accent |
| Neutrals | `#f0f4f8 → #1b2848` | – | 8-step ramp `bg → fg-1` |

**Gradient rule (from brandbook):** angles between **45° and 115°**. **Never 90°.** Three named gradients are pre-defined in `colors_and_type.css` (`--grad-blue`, `--grad-red`, `--grad-warning`), all at `105deg`.

### Typography

- **Roboto** (display + body, 300 / 400 / 500 / 700) — self-hosted under `fonts/`.
- **Roboto Condensed** (400, 700) — used for headings, table headers, badge labels, numeric/barcode tokens. Acts as the "display" face *and* the de-facto monospace for IDs.
- (Brandbook also references **Roboto Slab** and **TT Hoves**, but the codebase ships only Roboto + Condensed; we follow the codebase.)
- **Scale:** 11 / 12 / 13 / 14 / 16 / 18 / 22 / 28 / 36. Default body = 13–14 px. Headings 16–22 px. **TSD primary actions ≥ 16 px**, hit areas ≥ 44 px.
- **Casing:** Sentence case for buttons; **UPPERCASE + .5px letter-spacing** for eyebrow/field labels (`.eyebrow`).

### Spacing & layout

- 4-px base. Most padding lives at 8 / 12 / 16 / 20 / 24 px.
- **Cards:** 1 px solid `--border-soft` border, `--r-md (8px)` radius, `--shadow-md`. Inner padding 16–20 px.
- **Tables:** 9–10 px row padding, 1 px `--border-line` separators, header in `Roboto Condensed` 11 px UPPERCASE on `--surface-alt` (light) or `--brand-ink` (dense legacy table).
- **Touch:** TSD CTAs are `--hit-cta (56px)`, secondary actions `--hit-min (44px)`.

### Backgrounds & imagery

- **No full-bleed photography.** No illustrations. No textures or grain.
- The web app uses a **flat tinted page background** (`#f0f4f8` / `#f2f5f9`).
- The only "decorative" surface is the **navbar gradient** (`--grad-blue`, 105°). Modals get a 45 % black scrim. Status pills are tint-on-tint solids.
- Brand bird mark (`assets/bird.svg`) is available but unused in the running UI; reserve for splash / login.

### Animation

- **Restrained.** Existing transitions are 120–180 ms `--ease` on `border-color`, `background`, `opacity`, `filter`.
- Single keyframe in code: `scan-flash` — 500 ms green flash on a freshly-scanned row.
- A spinner (`.spinner`) used as htmx busy indicator.
- **No bounces, no parallax, no spring physics.** Motion exists to confirm scans, not to delight.

### Hover / press / focus states

- **Hover:** `filter: brightness(1.1)` on filled buttons; `background: rgba(255,255,255,.08)` on dark navbar items; `border-color: var(--brand-blue)` on inputs/cards on hover.
- **Active / press:** `filter: brightness(.95)` on filled buttons.
- **Focus:** `box-shadow: var(--focus-ring)` (3 px `rgba(29,113,184,.25)` ring) plus blue border. Always visible — operators rely on keyboard / scanner focus.
- **Disabled:** `opacity: .45; cursor: not-allowed;`

### Borders, shadows, elevation

- Borders: 1 px solid `--border-soft (#dde4ef)` for surfaces; 1.5 px dashed `--warning-border` for `unseal-panel`; 1 px dashed `--brand-red` for danger zone.
- **Four-step shadow ramp** in `colors_and_type.css` (`--shadow-sm/md/lg/xl`), all tinted with `rgba(27,40,72, …)` so depth reads as ink, not pure black.
- Dropped/raised navbar uses `--shadow-nav` for a strong float against the page tint.
- **No inner shadows. No glow.**

### Borders vs capsules

- Pills (status / kind / count) are **fully rounded** (`--r-pill` / `999px`), tinted bg + matching ink text, 11 px UPPERCASE optional.
- Buttons are **softly rounded** (`--r-sm (6px)`).
- Cards and modals: **moderately rounded** (`--r-md (8px)` / `--r-lg (10px)`).

### Layout rules

- **Sticky top navbar** (height 48 px on web, dark gradient).
- **TSD layout (this design system's primary surface):**
  - Top app bar 56 px (ink-blue) with title + back/close.
  - Bottom-anchored primary CTA bar — full-width, 56 px tall, blue or green when an action is available, ink-grey when not.
  - Status pill **always visible** beside envelope number.
  - Scan target stays focused; on-screen keyboard suppressed for the scan field.
- Modals use a centred 440–520 px box with `--shadow-xl` on a 45 % black scrim.

### Transparency / blur

- Used **sparsely**, never blurred backgrounds. Only flat alpha on dark surfaces:
  - `rgba(255,255,255,.08–.16)` for hover tints on dark navbar.
  - `rgba(255,255,255,.10–.15)` for inset chips on dark.
- **No `backdrop-filter`** anywhere in the codebase.

### Imagery vibe

- N/A — there is no product photography or illustration. The brandbook bitmaps included under `assets/` are reference material only.

### Card anatomy

- **Web card:** 1 px solid `--border` + `--shadow-md` + `--r-sm/md` + 20×24 px padding + a `.card-title` row with `Roboto Condensed 16px 700` ink + 2 px bottom border.
- **TSD list-item card:** full-bleed row, 56–72 px tall, 16 px horizontal padding, 1 px bottom-divider only — no individual card chrome (saves vertical space on a 5–6" screen).

### Corner radii

`4 / 6 / 8 / 10 / 999` px. **6 px is the default** for buttons/inputs; **8 px** for cards/chips; **10 px** for modals; **999 px** for pills.

---

## Iconography

- **Icon system:** [Lucide](https://lucide.dev/) — used directly via the official CDN (`unpkg.com/lucide@latest/dist/umd/lucide.js`) in the web codebase. The TSD UI kit follows suit (so prototypes share a single visual language). All icon strokes are 1.8 px, 15 × 15 px in chrome / 13 × 13 px in dense lists.
- **Icons in active use** (lifted from `app/web/templates/base.html` + partials):
  `package-plus`, `scan-line`, `book-open`, `archive`, `file-text`, `circle-user`, `settings-2`, `log-out`, `lock-open`, `unlock`, `triangle-alert`, `info`, `history`, `user`, `clock`, `users`, `user-plus`, `trash-2`, `check`, `x`, `chevron-down`, `chevron-right`, `printer`, `wifi`, `wifi-off`, `qr-code`, `arrow-left`.
- **No emoji.** Brandbook is anti-emoji; codebase confirms — only Lucide icons appear in chrome.
- **No Unicode glyphs as icons** (no `✓` `→` etc.) — every glyph is rendered through Lucide for consistency.
- **Logo:** `assets/logo-icon.png` — a small white-on-transparent corporate icon, displayed at 32 × 32 in the navbar logo slot (and inside the splash on TSD).
- **Brand mark:** `assets/bird.svg` is preserved as a secondary mark; not currently placed in any active screen.
- **Substitutions flagged:** none. Lucide is the codebase's actual choice. *(See Caveats below for Roboto Slab / TT Hoves which are referenced in the brandbook but not in the codebase — we deliberately did not synthesise them.)*

---

## Caveats — please review

- **Roboto Slab + TT Hoves** are mentioned in the brandbook screenshots but no font files exist in the repo. This system uses **Roboto + Roboto Condensed only** (matching the codebase). If Slab/TT Hoves should be available for marketing surfaces, please attach the files.
- **No Android-native source** was provided for the TSD app — only the project-overview spec ("v1.2: native Android client"). The TSD UI kit is a high-fidelity HTML mock that mirrors the web tokens; component naming follows Compose conventions (`AppBar`, `BottomCta`, `ListItem`) so it can be ported.
- **Logo asset** (`assets/logo-icon.png`) is the codebase's `icon.png` — the file shipped in the repo appears mostly white/transparent against a light background. If a richer logo lockup exists, please attach.

---

This README is the index. Open the cards in the **Design System** tab to review tokens and components in isolation, then open `ui_kits/tsd_android/index.html` for the interactive prototype.
