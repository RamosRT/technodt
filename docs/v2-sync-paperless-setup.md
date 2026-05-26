# Конверт-трек v2: настройка локального зеркала 1С и Paperless

Документ описывает запуск локального зеркала документов 1С, регулярную синхронизацию и интеграцию с Paperless-ngx/ТехноАрхивом.

## Что появилось в v2

- Таблица `onec_documents` хранит локальную копию документов `Document_СчетФактураВыданный`.
- Первичное заполнение выполняется вручную через `POST /api/admin/sync/initial`.
- Инкрементальная синхронизация запускается автоматически по расписанию APScheduler и вручную через `POST /api/admin/sync/incremental`.
- Paperless post-consume webhook отправляет событие в Конверт-трек.
- Конверт-трек ищет документ по типу, дате и номеру (из имени файла), отмечает архивный статус локально и PATCH-ит ссылку в 1С в `kzvСсылкаНаКопию`.
- При ошибке матчинга или PATCH в 1С webhook ставит в Paperless тег `PAPERLESS_ERROR_TAG_ID` (на проде обычно **8**); при успехе снимает теги «Отметить в 1С» и «Ошибка».

## 1. Настроить `.env` на сервере Конверт-трек

Файл находится в корне репозитория: `E:\technodt\.env`. Не коммитить его.

Минимальный блок для БД, 1С, администратора, синхронизации и Paperless:

```env
ENV=production

DATABASE_URL=postgresql+asyncpg://convert_track:<PASSWORD>@localhost:5432/convert_track

ODATA_BASE_URL=http://<1c-host>/<base>/odata/standard.odata
ODATA_ADMIN_USER=<readonly-odata-user>
ODATA_PASSWORD=<readonly-odata-password>
ODATA_TIMEOUT_SECONDS=60

ADMIN_LOGIN=admin
ADMIN_PASSWORD=<4-digit-pin>

PAPERLESS_WEBHOOK_API_KEY=<long-random-shared-token>
PAPERLESS_API_URL=http://<paperless-host>:8000
PAPERLESS_API_TOKEN=<paperless-user-api-token>
PAPERLESS_MARK_TAG_ID=52
PAPERLESS_ERROR_TAG_ID=53
PAPERLESS_ONEC_ORIGINALS_UNC_ROOT=\\kaz-pc036\Техно-Архив
PAPERLESS_ONEC_ARCHIVE_UNC_ROOT=
PAPERLESS_POLL_INTERVAL_MINUTES=0
PAPERLESS_POLL_BATCH_SIZE=50
SYNC_INITIAL_FROM_DATE=2023-01-01
SYNC_SCHEDULE_HOURS=4
```

Переменные:

- `DATABASE_URL` - основная PostgreSQL база Конверт-трек.
- `ODATA_BASE_URL` - корень 1С OData, должен заканчиваться на `/odata/standard.odata`.
- `ODATA_ADMIN_USER`, `ODATA_PASSWORD` - техническая учётка 1С с доступом на чтение и PATCH поля `kzvСсылкаНаКопию`.
- `ADMIN_LOGIN`, `ADMIN_PASSWORD` - bootstrap-администратор для web/API.
- `PAPERLESS_WEBHOOK_API_KEY` - общий секрет между Paperless и Конверт-трек. Используется как `Authorization: Bearer ...`.
- `PAPERLESS_API_URL`, `PAPERLESS_API_TOKEN` - доступ Конверт-трека к Paperless API для обработки документов по тегу.
- `PAPERLESS_MARK_TAG_ID` - тег Paperless "Отметить в 1С"; документы с ним забирает обработчик.
- `PAPERLESS_ERROR_TAG_ID` - тег Paperless "Ошибка отметки в 1С"; ставится при ошибке матчинга или PATCH в 1С.
- `PAPERLESS_ONEC_ORIGINALS_UNC_ROOT` - UNC-root, который пишется в `kzvСсылкаНаКопию` для файлов из `metadata.media_filename`.
- `PAPERLESS_POLL_INTERVAL_MINUTES=0` выключает автополлинг. Поставить `1`, `5` и т.п., если нужно регулярное фоновое отслеживание.
- `SYNC_INITIAL_FROM_DATE` - с какой даты грузить документы при первичном заполнении.
- `SYNC_SCHEDULE_HOURS` - период авто-синхронизации в часах. `4` означает каждые 4 часа. `0` отключает scheduler.

## 2. Применить миграции

На сервере Конверт-трек:

```powershell
cd E:\technodt
venv\Scripts\python -m alembic upgrade head
```

Ожидаемо должна примениться миграция `0008 -> onec_documents`, если она ещё не применена.

## 3. Запустить приложение

Для ручной проверки:

```powershell
cd E:\technodt
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Для production через `nssm`:

```powershell
nssm install ConvertTrack "E:\technodt\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 127.0.0.1 --port 8080"
nssm set ConvertTrack AppDirectory E:\technodt
nssm start ConvertTrack
```

Важно: scheduler инкрементальной синхронизации стартует вместе с FastAPI, если `SYNC_SCHEDULE_HOURS > 0`.

## 4. Первично заполнить локальную БД из 1С

Сначала получить cookie администратора:

```powershell
curl.exe -i -c cookies.txt -X POST http://127.0.0.1:8080/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"admin\",\"password\":\"0000\"}"
```

Заменить `admin` и `0000` на значения `ADMIN_LOGIN` и `ADMIN_PASSWORD`.

Запустить initial sync:

```powershell
curl.exe -b cookies.txt -X POST http://127.0.0.1:8080/api/admin/sync/initial
```

Проверять статус:

```powershell
curl.exe -b cookies.txt http://127.0.0.1:8080/api/admin/sync/status
```

Статусы:

- `running` - загрузка идёт;
- `done` - загрузка завершена;
- `error` - ошибка, смотреть лог uvicorn/службы.

Первичная загрузка идёт постранично по 1000 документов, начиная с `SYNC_INITIAL_FROM_DATE`.

## 5. Инкрементальная синхронизация

Автоматически:

- включена, если `SYNC_SCHEDULE_HOURS > 0`;
- период задаётся в часах;
- при запуске берёт дату запрета изменения из 1С и перечитывает документы от этой даты до сегодня;
- включает помеченные на удаление, чтобы локальный кэш мог обновить `is_deleted`.

Вручную:

```powershell
curl.exe -b cookies.txt -X POST http://127.0.0.1:8080/api/admin/sync/incremental
```

Если уже идёт другая синхронизация, API вернёт `409 sync already running`.

## 6. Проверить отчёт документов

В web UI войти администратором и открыть вкладку `Отчёт`.

API:

```powershell
curl.exe -b cookies.txt "http://127.0.0.1:8080/api/report/documents?page_size=5"
```

CSV:

```powershell
curl.exe -b cookies.txt -o document-report.csv "http://127.0.0.1:8080/api/report/documents?page_size=10000&format=csv"
```

## 7. Настроить Paperless post-consume webhook

На сервере Paperless положить скрипт из репозитория:

```bash
sudo mkdir -p /opt/scripts
sudo cp scripts/paperless_post_consume.sh /opt/scripts/konvertrek_post_consume.sh
sudo chmod +x /opt/scripts/konvertrek_post_consume.sh
```

Если Paperless находится на другом сервере, перенести содержимое `E:\technodt\scripts\paperless_post_consume.sh` на Paperless-сервер вручную.

В `paperless.conf`, `.env` или `docker-compose.env` Paperless добавить:

```env
PAPERLESS_POST_CONSUME_SCRIPT=/opt/scripts/konvertrek_post_consume.sh
KONVERTREK_URL=http://10.60.6.11:8080
KONVERTREK_API_KEY=<same value as PAPERLESS_WEBHOOK_API_KEY>
KONVERTREK_ONEC_ORIGINALS_UNC_ROOT=\\kaz-pc036\Техно-Архив
# optional, defaults to KONVERTREK_ONEC_ORIGINALS_UNC_ROOT
KONVERTREK_ONEC_ARCHIVE_UNC_ROOT=
```

`KONVERTREK_URL` должен быть доступен с Paperless-сервера. Если приложение слушает только `127.0.0.1`, опубликовать порт на нужном интерфейсе или настроить reverse proxy до `127.0.0.1:8080`.

Hook передаёт `document_id`; Конверт-трек запрашивает Paperless metadata и собирает UNC из
`metadata.media_filename` + `PAPERLESS_ONEC_ORIGINALS_UNC_ROOT` (то же, что при обработке по тегу).
Hook может передать запасной `archive_path` из `DOCUMENT_ARCHIVE_PATH` / `DOCUMENT_SOURCE_PATH`, если API Paperless недоступен.
Если путь находится внутри `/usr/src/paperless/media/documents/archive/` или `/usr/src/paperless/media/documents/originals/`,
скрипт заменяет контейнерный префикс на `KONVERTREK_ONEC_ARCHIVE_UNC_ROOT` или `KONVERTREK_ONEC_ORIGINALS_UNC_ROOT`, чтобы в 1С попал Windows/UNC-путь.

После изменения настроек перезапустить Paperless.

## 8. Проверить webhook вручную

С сервера Paperless или любой машины, которая видит Конверт-трек:

```bash
curl -s -X POST http://10.60.6.11:8080/api/webhooks/paperless \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <PAPERLESS_WEBHOOK_API_KEY>" \
  -d '{"doc_type":"доверенность","created":"2026-01-01"}'
```

Ожидаемо:

```json
{"status":"skipped","reason":"not an invoice type: 'доверенность'"}
```

Для реального УПД/УКД Paperless должен передать:

- `doc_type` - одно из `упд`, `укд`, `упд/укд`;
- `created` - дата документа;
- `file_name` или `original_filename` - имя, из которого можно извлечь номер после `№`;
- `correspondent` - контрагент;
- `download_url` - ссылка на скачивание в Paperless;
- `archive_path` - UNC/путь к архивному файлу, если Paperless его передаёт.

## 9. Backfill существующих документов Paperless

Перед реальным импортом выполнить dry-run:

```powershell
cd E:\technodt
venv\Scripts\python scripts\paperless_bulk_import.py `
  --paperless-url http://<paperless-host>:8000 `
  --paperless-token <PAPERLESS_API_TOKEN> `
  --konvertrek-url http://10.60.6.11:8080 `
  --konvertrek-key <PAPERLESS_WEBHOOK_API_KEY> `
  --onec-originals-unc-root "\\kaz-pc036\Техно-Архив" `
  --dry-run
```

Проверить:

- какие типы документов Paperless вернул;
- сколько документов попало в `invoice_type_matches`;
- сколько событий получили `archive_path` (`Events with archive_path`);
- совпадают ли названия типов с `упд`, `укд`, `упд/укд`.

`--onec-originals-unc-root` - это путь, который должен попасть в 1С в поле `kzvСсылкаНаКопию`.
Paperless API отдаёт относительный `metadata.media_filename`, а скрипт собирает UNC так:

```text
\\kaz-pc036\Техно-Архив + \2026\03\02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf
```

Итог для 1С:

```text
\\kaz-pc036\Техно-Архив\2026\03\02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf
```

Можно не передавать параметр каждый раз, а задать переменную окружения:

```powershell
$env:PAPERLESS_ONEC_ORIGINALS_UNC_ROOT="\\kaz-pc036\Техно-Архив"
```

Если Paperless уже передаёт полный путь вида
`\\paperless-server\paperless-media\documents\originals\...`, можно включить замену prefix:

```powershell
--replace-unc-from "\\paperless-server\paperless-media\documents\originals" `
--replace-unc-to "\\kaz-pc036\Техно-Архив"
```

Если типы называются иначе, добавить их явно:

```powershell
venv\Scripts\python scripts\paperless_bulk_import.py `
  --paperless-url http://<paperless-host>:8000 `
  --paperless-token <PAPERLESS_API_TOKEN> `
  --konvertrek-url http://10.60.6.11:8080 `
  --konvertrek-key <PAPERLESS_WEBHOOK_API_KEY> `
  --onec-originals-unc-root "\\kaz-pc036\Техно-Архив" `
  --invoice-type "УПД" `
  --invoice-type "УКД" `
  --invoice-type "УПД/УКД" `
  --dry-run
```

Реальный запуск:

```powershell
venv\Scripts\python scripts\paperless_bulk_import.py `
  --paperless-url http://<paperless-host>:8000 `
  --paperless-token <PAPERLESS_API_TOKEN> `
  --konvertrek-url http://10.60.6.11:8080 `
  --konvertrek-key <PAPERLESS_WEBHOOK_API_KEY> `
  --onec-originals-unc-root "\\kaz-pc036\Техно-Архив"
```

В конце смотреть статистику:

- `matched` - документ найден в локальном зеркале и отмечен как архивный;
- `not_matched` - документ Paperless не сопоставился с локальным документом;
- `skipped` - тип документа не УПД/УКД.

Если много `not_matched`, проверить:

- завершилась ли initial sync;
- правильная ли дата в Paperless;
- есть ли номер документа в имени после `№`;
- совпадает ли контрагент с `partner_name` из 1С;
- не отличается ли тип документа в Paperless от ожидаемых названий.

## 9.1. Обработка существующих документов по тегу Paperless

В Paperless используются теги:

- `Отметить в 1с`, id `52`;
- `Ошибка отметки в 1С`, id `53`.

Сценарий:

1. В Paperless поставить документам тег `Отметить в 1с`.
2. В Конверт-треке открыть `Настройки -> Система`.
3. Нажать `Paperless: отметка в 1С -> Обработать сейчас`.
4. Для каждого документа обработчик:
   - получает документ и metadata из Paperless API;
   - строит UNC путь для 1С из `metadata.media_filename`;
   - ищет документ в `onec_documents` по дате, номеру и корреспонденту;
   - пишет `archive_storage_path`, `archive_download_url`, `kzv_copy_link` в локальную БД;
   - отправляет PATCH в 1С `kzvСсылкаНаКопию`;
   - после успеха снимает тег `Отметить в 1с`;
   - при ошибке ставит тег `Ошибка отметки в 1С`.

Автоматический запуск включается через:

```env
PAPERLESS_POLL_INTERVAL_MINUTES=5
```

После изменения `.env` перезапустить службу/uvicorn.

## 10. Что проверить после интеграции

1. В отчёте Конверт-трек у документов появляются дата и ссылка `ТехноАрхив`.
2. В таблице `onec_documents` заполнены:
   - `archive_processed_at`;
   - `archive_storage_path`;
   - `archive_download_url`;
   - `kzv_copy_link`.
3. В 1С у найденных документов заполнено поле `kzvСсылкаНаКопию`, если Paperless передал `archive_path`.
4. Новые документы Paperless после потребления автоматически вызывают webhook.
5. Инкрементальная синхронизация не падает в логах службы.

## 11. Безопасность

- `PAPERLESS_WEBHOOK_API_KEY` должен быть длинным случайным значением и совпадать только между `.env` Конверт-трек и настройками Paperless.
- Не публиковать webhook без firewall/reverse proxy ограничений, если сервер доступен извне.
- `.env`, Paperless token и реальные OData credentials не коммитить и не вставлять в задачи/чат.
- `/api/admin/sync/*` требует admin cookie, но всё равно должен быть доступен только из доверенной сети.
