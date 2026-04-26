# Конверт-трек MVP — design spec

**Дата:** 2026-04-26
**Источники:** `project-overview.md` (полный замысел), `development.md` (исходная постановка), брендбук в `design/` (палитра, шрифты), брейншторм в текущей сессии (закрытые вопросы по средам и подходам).

Эта спецификация фиксирует решения, принятые на этапе брейншторма поверх `project-overview.md`. Она — источник правды для последующего плана реализации (`writing-plans`).

---

## 1. Scope MVP

В MVP входит:
- Регистрация конверта оператором (черновик → последовательное добавление документов через сканер → запечатывание с выбором подписантов и филиалов → печать описи и этикетки).
- Сверка конверта на точке получения (сканирование ШК конверта → подсветка совпадающих документов → завершение со статусом `verified` или `verified_with_discrepancy`).
- Редактирование состава конверта до запечатывания (удаление документа крестиком в UI).
- Минимальные справочники подписантов и филиалов с inline-редактированием.
- Печать: PDF описи (через xlsx-шаблон + LibreOffice headless) и PDF этикетки ШК (ReportLab).
- Soft-аутентификация (имя оператора в cookie) + админ-токен для `/api/admin/*`.
- Интеграция с 1С OData через httpx с пробой типов документа.
- Развёртывание в двух режимах: dev в Docker Compose, прод как Windows-служба через nssm.

**Сознательно отложено:**
- Список конвертов с фильтрами и UI просмотр `audit_log` (v1.1).
- Полноценные пользователи с ролями и bcrypt (v1.1).
- Android-клиент и прямая ZPL-печать (v1.2).
- Оффлайн-режим ТСД, аналитика, уведомления (v2).

## 2. Архитектура и структура проекта

```
E:\technodt\
├── app/
│   ├── main.py                 # FastAPI, монтирует роутеры и static
│   ├── config.py               # pydantic-settings, читает .env
│   ├── db.py                   # async SQLAlchemy engine + session
│   ├── auth.py                 # cookie с именем оператора + dep на admin токен
│   ├── models/                 # SQLAlchemy модели
│   ├── schemas/                # pydantic схемы для API
│   ├── services/
│   │   ├── envelopes.py        # бизнес-логика
│   │   ├── odata.py            # клиент 1С с пробой типов документа
│   │   ├── barcode.py          # barcode_to_guid, генератор номера/ШК
│   │   └── audit.py            # запись в audit_log
│   ├── printing/
│   │   ├── description.py      # xltpl → xlsx → LibreOffice → PDF
│   │   ├── label.py            # ReportLab → PDF этикетки
│   │   └── soffice.py          # обёртка над soffice --headless
│   ├── routers/
│   │   ├── api/                # JSON-эндпоинты (для будущего Android и тестов)
│   │   └── ui/                 # HTMX-фрагменты
│   └── web/
│       ├── templates/          # Jinja2: index.html, partials/*
│       └── static/             # app.js (~80 строк сканер), style.css, шрифты
├── templates/
│   └── envelope_description.xlsx   # xltpl-шаблон описи (правится в Excel)
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── fixtures/odata/         # JSON-фикстуры ответов 1С
│   └── test_*.py
├── design/                     # брендбук + шрифты + иконка (уже на месте)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
├── .gitignore
├── CLAUDE.md
├── project-overview.md
├── development.md
├── odata_metadata.xml
└── README.md
```

**Архитектурные решения:**

1. **Слои:** routers (HTTP) → services (бизнес) → models (БД). OData-клиент и принтинг — отдельные сервисы, чтобы routers их не знали напрямую.
2. **`/api/*` и `/ui/*` разделены явно.** `/api/*` — JSON, контракт для Android v1.2 и тестов. `/ui/*` — HTML-фрагменты для HTMX, ходит только веб-страница. Бизнес-логика в `services/*` общая, роутеры тонкие.
3. **Async везде:** SQLAlchemy 2.x async, httpx async, FastAPI async-эндпоинты. LibreOffice — единственное синхронное место, запускается через `asyncio.create_subprocess_exec` без блокировки event loop.
4. **Конфиг через pydantic-settings:** все переменные `.env` валидируются на старте; падаем громко при отсутствии обязательных.
5. **Зависимости:** `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `httpx`, `jinja2`, `python-multipart`, `xltpl`, `reportlab`, `pytest`, `pytest-asyncio`, `respx`. HTMX — через CDN.

## 3. Модель данных

### Таблицы

```
branches              signers
─────────             ─────────
id (uuid PK)          id (uuid PK)
name (varchar)        last_name (varchar)
is_active (bool)      first_name (varchar)
created_at            is_active (bool)
                      created_at

envelopes
─────────
id (uuid PK)
number (varchar, unique)              # формат «ТА-NNNN…», 16 цифр после префикса
barcode (varchar, unique, indexed)    # Code128, 16 цифр без префикса
status (enum)                         # draft | sealed | verified | verified_with_discrepancy
created_at, sealed_at, verified_at (timestamptz)
created_by (varchar)                  # имя оператора из cookie
verified_by (varchar, null)           # имя оператора, проводившего проверку
origin_branch_id (uuid, FK→branches, null)        # задаётся при seal
destination_branch_id (uuid, FK→branches, null)   # задаётся при seal
signer_sender_id (uuid, FK→signers, null)         # «Сдал» — задаётся при seal
signer_receiver_id (uuid, FK→signers, null)       # «Принял» — задаётся при seal
notes (text, null)

envelope_documents
─────────
id (uuid PK)
envelope_id (uuid, FK→envelopes, ondelete cascade, indexed)
doc_barcode (varchar, indexed)
doc_guid (uuid)
doc_type (varchar)                    # имя сущности OData
doc_number (varchar)
doc_date (date)
related_realization_number (varchar, null)
raw_1c_payload (jsonb)
added_at (timestamptz)
scanned_at_verification (timestamptz, null)
UNIQUE(envelope_id, doc_guid)

audit_log
─────────
id (bigserial PK)
envelope_id (uuid, FK→envelopes, null, indexed)
event (varchar)                       # create | add_doc | remove_doc | seal |
                                      # verify_start | verify_scan | verify_finish |
                                      # reset | dictionary_change
payload (jsonb)
actor (varchar)
at (timestamptz, indexed)
```

### Инварианты

- **Иммутабельность после seal.** Изменения `envelope_documents` разрешены только при `status='draft'`. Проверка в сервис-слое (единственная точка входа); триггер не делаем.
- **Уникальность ШК конверта** — DB-constraint + retry-петля в `generate_unique_envelope_codes` (5 попыток).
- **Двойной скан** — `UNIQUE(envelope_id, doc_guid)` → 409 «уже добавлен».
- **Cascade удаления:** удалить конверт → удалятся документы. Справочники нельзя удалить если на запись есть ссылки (RESTRICT) — UI делает soft delete через `is_active=false`.
- **`raw_1c_payload`** — полный ответ OData кэшируется навсегда. Конверт остаётся самодостаточным даже при недоступной 1С.

### Миграции

Одна начальная миграция Alembic `0001_initial.py` создаёт все 5 таблиц, enum `envelope_status`, индексы. Никаких seed-данных.

## 4. HTTP API

### `/api/*` — JSON

**Конверты:** во всех мутирующих эндпоинтах имя оператора берётся из cookie soft-сессии (`operator_name`), а не из body. На уровне dependency: если cookie нет — 401 `operator_required` с предложением UI ввести имя.

```
POST /api/envelopes
  body: {}                       (имя оператора из cookie → пишется в created_by)
  201 → {"id", "number", "barcode", "status": "draft", "created_at"}

GET /api/envelopes/{id}
  200 → полный объект envelope с вложенными branches, signers, documents

GET /api/envelopes/by-barcode/{barcode}
  200 → объект | 404 envelope_not_found

POST /api/envelopes/{id}/documents
  body: {"barcode": "...39 цифр..."}
  201 → карточка документа
  400 barcode_invalid / 404 document_not_in_1c / 409 envelope_not_draft |
  409 document_already_in_envelope / 502 1c_unavailable

DELETE /api/envelopes/{id}/documents/{doc_id}
  204 / 409 envelope_not_draft

POST /api/envelopes/{id}/seal
  body: {"signer_sender_id", "signer_receiver_id",
         "origin_branch_id", "destination_branch_id", "notes"}
  200 → envelope (status=sealed)
  400 invalid_seal_payload   (отсутствуют id / неактивные signer/branch / документов 0)
  409 envelope_not_draft     (включая случай envelope_already_sealed)
```

**Сверка:**
```
POST /api/envelopes/{id}/verify/start
  body: {}                   (имя оператора из cookie → пишется в verified_by)
  200 → envelope; в audit_log пишется verify_start

POST /api/envelopes/{id}/verify/scan
  body: {"barcode"}
  200 → {"matched": true, "doc_id", "scanned_at"} | {"matched": false, "reason": "not_in_envelope"}

POST /api/envelopes/{id}/verify/finish
  body: {"force": false}
  200 → {"status": "verified" | "verified_with_discrepancy", "missing_docs": [...]}
  409 verification_unscanned (если force=false и есть несканированные)
```

**Печать:**
```
GET /api/envelopes/{id}/print/description    → application/pdf
GET /api/envelopes/{id}/print/label          → application/pdf
```
До seal — PDF с водяным знаком «DRAFT».

**Справочники:**
```
GET    /api/branches?active=true
POST   /api/branches              body: {"name"}
PATCH  /api/branches/{id}         body: {"is_active": false}
GET    /api/signers?active=true
POST   /api/signers               body: {"last_name", "first_name"}
PATCH  /api/signers/{id}          body: {"is_active": false}
```

**Админ (требует `X-Admin-Token`):**
```
POST /api/admin/reset
  body: {"confirm": "I_KNOW_WHAT_I_DO"}
  В проде (ENV=production) → 404
```

### `/ui/*` — HTMX-фрагменты

```
GET  /                                          # главная: две большие кнопки
POST /ui/envelopes                              # «Новый конверт» → блок карточки
POST /ui/envelopes/{id}/documents               # скан документа → новая <tr>
DELETE /ui/envelopes/{id}/documents/{doc_id}    # крестик → удалённая <tr>
GET  /ui/envelopes/{id}/seal-form               # модалка с выпадашками
POST /ui/envelopes/{id}/seal                    # submit модалки → блок «успех + печать»
POST /ui/envelopes/by-barcode                   # вход в режим verify
POST /ui/envelopes/{id}/verify/scan             # скан в verify → подкрашенная <tr>
POST /ui/envelopes/{id}/verify/finish           # «Завершить»
GET/POST/PATCH /ui/dictionaries/{branches,signers}/...   # inline-редактирование
```

### Сериализация ошибок

Все 4xx/5xx — `{"detail": "...", "code": "machine_readable_code"}`. Коды:
`barcode_invalid`, `document_not_in_1c`, `1c_unavailable`, `envelope_not_draft`, `envelope_not_found`, `document_already_in_envelope`, `verification_unscanned`, `invalid_seal_payload`, `admin_token_invalid`, `operator_required`.

## 5. Ключевые алгоритмы

### 5.1. Barcode → GUID 1С
```python
def doc_barcode_to_guid(barcode: str) -> uuid.UUID:
    if not barcode.isdigit(): raise BarcodeError("barcode_invalid")
    n = int(barcode)
    if n.bit_length() > 128: raise BarcodeError("barcode_invalid")
    return uuid.UUID(bytes=n.to_bytes(16, "big"))
```

### 5.2. Генерация номера и ШК конверта
- `number` = `ТА-` + 16 цифр (человекочитаемый).
- `barcode` = те же 16 цифр **без префикса** (для плотности Code128 на этикетке).
- `secrets.choice` (криптостойкий RNG), retry на `IntegrityError` до 5 попыток. Коллизии на 16 цифрах ≈ 10⁻¹⁶.

### 5.3. OData-клиент с пробой типов
```python
KNOWN_DOC_TYPES = (
    "Document_ПеремещениеТоваров",
    "Document_СчетФактураВыданный",
)   # порядок = частота в проде; пересортируется по статистике audit_log
```
Последовательная проба, не параллельная (50-документный конверт перегрузит 1С). На 200 — возвращаем `(doc_type, payload)`. На 404 — следующий тип. На 401 — `OneCUnavailable("auth failed")` (отдельная диагностика). На `ConnectError`/`ReadTimeout` после всех попыток — `OneCUnavailable`. Если все вернули 404 — `DocumentNotFound`.

Один общий `httpx.AsyncClient` на приложение, базовая авторизация, инициализируется в FastAPI lifespan.

### 5.4. Сканер-логика на клиенте

`app/web/static/app.js`, ~80 строк, без сборки. Поведение:
- Скрытый `<input id="scanner-buffer" autofocus>` ловит весь ввод сканера.
- Focus trap: любой клик мимо input/select/textarea/button возвращает фокус.
- На `Enter` — диспетчеризация по `mode`:
  - `register`: длина 16 и все цифры → запечатываем (это собственный ШК конверта); иначе — добавляем как ШК документа через `htmx.ajax`.
  - `verify`: ищем строку с `data-doc-barcode={value}` и обновляем outerHTML через `/ui/.../verify/scan`.
  - `await_envelope_seal`: переход в режим verify через `/ui/envelopes/by-barcode`.
- Различение «ШК документа» vs «ШК конверта» — по длине = 16. Запасной план если в проде вылезут 16-значные ШК документов: настраиваемый префикс `ENVELOPE_BC_PREFIX=99` через env.

### 5.5. Печать описи
```python
async def render_description_pdf(envelope) -> bytes:
    ctx = build_context(envelope)
    xlsx_path = tmp / f"{envelope.id}.xlsx"
    BookWriter("templates/envelope_description.xlsx").render_book(
        payloads=[{"sheet_name": "Опись", "ctx": ctx}]
    ).save(str(xlsx_path))
    pdf_path = await soffice.convert_to_pdf(xlsx_path)
    return pdf_path.read_bytes()
```
Временные файлы в `tempfile.TemporaryDirectory`, удаляются после ответа. Таймаут soffice 30 секунд → kill + 500 с понятным сообщением. `SOFFICE_PATH` через env (`/usr/bin/soffice` в Docker, путь к LibreOffice Portable в проде).

### 5.6. Этикетка ШК
ReportLab, 58×40 мм, Code128 + номер + дата, цвета и шрифты из брендбука. Roboto регистрируется один раз через `pdfmetrics.registerFont` при старте приложения.

## 6. Тестирование

- **Unit:** barcode-конвертация, генерация номера/ШК, нормализация payload OData (без БД).
- **Сервис-тесты:** полные сценарии create→add→seal→verify против реальной dockerized Postgres.
- **API-тесты `/api/*`:** каждый эндпоинт, happy + каждый код ошибки. `respx` мокает 1С.
- **Тесты `/ui/*`:** проверка что HTML-фрагмент содержит ожидаемые маркеры (без CSS-проверок).
- **Печать:** проверка что PDF начинается с `%PDF-`. Содержание не парсим.
- **Сканер `app.js`:** не тестируем автоматически в MVP — ручной чек-лист в `docs/testing.md`.
- Запуск: `pytest -x`, цель `< 30 сек`.

**Фикстуры OData:** на старте — синтетические, выведенные из `odata_metadata.xml` (EDMX-схема). Когда пользователь подключит туннель отдельно от сессии Claude и пришлёт реальные ответы для каждого `Document_*` типа — кладём в `tests/fixtures/odata/real_*.json` и парсер перепрогоняется.

## 7. Развёртывание

### Dev — Docker Compose

`docker-compose.yml` поднимает `postgres:16` + `app` (Python 3.14-slim + libreoffice-calc + Roboto fonts). Маунт исходников + `--reload` uvicorn. Команды разработчика: `docker compose up`, `docker compose run --rm app pytest`, `docker compose run --rm app alembic upgrade head`.

### Прод — Windows Server + nssm

1. `python -m venv E:\technodt\venv` (Python 3.14, уже стоит).
2. `venv\Scripts\pip install -e .`
3. Установить LibreOffice (полный установщик с офсайта или Portable в `E:\LibreOffice`); `SOFFICE_PATH` в `.env`.
4. `.env` рядом с проектом — реальные креды OData, `DATABASE_URL`, сильный `ADMIN_TOKEN`, `ENV=production`.
5. `venv\Scripts\alembic upgrade head`.
6. nssm install + AppDirectory + AppStdout/Stderr с ротацией 10 МБ + start.
7. Опционально — Apache `mod_proxy` пробрасывает `https://host/convert-track/ → 127.0.0.1:8080`.
8. `pg_dump` + Task Scheduler ежедневно, держим 7 копий — инструкция в `README.md`.

## 8. Брендирование

Извлечено из `design/Screenshot_4-6.png`:

| Цвет | Hex | Использование |
|---|---|---|
| Чернильный (PANTONE 2768 C) | `#1b2848` | основной тёмный (header, кнопки primary) |
| Голубой (PANTONE 285 C) | `#1d71b8` | акцент / ссылки / второстепенные кнопки |
| Светло-голубой (PANTONE 284 C) | `#6ea9dc` | фоны, hover-состояния |
| Алый (PANTONE 485 C) | `#e4032e` | ошибки, расхождения при verify |
| Зелёный (RAL 6039) | `#a5c715` | успех (отсканированный документ при verify) |

Шрифты: Roboto (основной, все начертания в `design/Roboto/`), Roboto Condensed (плотные таблицы, `design/Roboto_Condensed/`). На вебе — `@font-face` в `style.css`, на этикетке — `pdfmetrics.registerFont` для ReportLab.

## 9. Риски и митигации

| Риск | Митигация |
|---|---|
| LibreOffice headless зависает раз в N запусков | таймаут 30 с + kill + повторный запрос; в v1.1 — pool/aspose |
| ШК конверта 16 цифр конфликтует с 16-значным ШК документа | `ENVELOPE_BC_PREFIX=99` через env, включается при коллизии |
| Порядок проб OData неоптимален | в `audit_log` пишем сработавший тип, периодически пересортируем `KNOWN_DOC_TYPES` |
| `xltpl` не справится со сложным шаблоном (мерджи, картинки) | план B — `openpyxl` с ручными вставками строк |
| Cyrillic в URL OData ломается на прокси | httpx percent-кодит автоматически; запасной план — ASCII-алиас сервиса |
| Сканер не шлёт `Enter` | UI-конфиг «терминатор: Enter / Tab / Auto», localStorage |
| Postgres недоступен на старте | uvicorn exit; nssm рестарт; чёткая ошибка в логах |
| Конверт «застрял» в sealed | в v1.1 — отчёт «не сверенные > X дней» |

## 10. Что точно не входит в MVP

- Список конвертов с фильтрами и просмотр audit_log в UI (v1.1).
- Полноценные пользователи + bcrypt + роли (v1.1).
- Android-клиент, прямая ZPL-печать (v1.2).
- Оффлайн-режим, аналитика, нотификации (v2).
- Автоматизированные UI/E2E-тесты сканер-логики (v1.1, через Playwright).
