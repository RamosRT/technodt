# Android TSD App — Design Spec
**Дата:** 2026-05-04  
**Проект:** Конверт-трек (ТехноКонверт) v1.2  
**Устройства:** Urovo i6310, Urovo DT40, Mindeo M40

---

## 1. Контекст

Backend (FastAPI + PostgreSQL) и веб-клиент оператора уже готовы (MVP + v1.1). Этот документ описывает нативный Android-клиент для ТСД — v1.2 по roadmap.

Функционально приложение повторяет веб-клиент: регистрация конвертов и сверка содержимого. Интерфейс адаптирован под ТСД: крупные кнопки, встроенный сканер через Intent API, печать ZPL через backend.

---

## 2. Расположение проекта

```
E:\technodt\
  android/          ← корень Android-проекта (Gradle)
  app/              ← существующий Python backend
  design/system/    ← дизайн-система (референс)
```

Android-проект живёт в `android/` внутри того же git-репозитория.

---

## 3. Стек технологий

| Компонент | Выбор |
|---|---|
| Язык | Kotlin |
| UI | Jetpack Compose + Material 3 |
| DI | Hilt |
| Навигация | Compose Navigation |
| Сеть | Retrofit 2 + OkHttp + Gson |
| Async | Kotlin Coroutines + StateFlow |
| Хранение настроек | Jetpack DataStore (Preferences) |
| Звук | SoundPool |
| Иконки | Lucide (SVG → res/drawable) |
| MinSdk | 26 (Android 8.0) |
| TargetSdk | 34 |

---

## 4. Структура проекта

```
android/
  app/
    src/main/
      java/ru/technoavia/konverttrack/
        data/
          api/            # Retrofit интерфейсы + DTO
          repository/     # EnvelopeRepository, PrinterRepository
          scanner/        # ScannerManager интерфейс + реализации
          prefs/          # DataStore: serverUrl, operatorToken, printerId
        domain/
          model/          # Envelope, Document, Printer (чистые data class)
          usecase/        # AddDocumentUseCase, SealEnvelopeUseCase, VerifyUseCase
        ui/
          theme/          # Color.kt, Type.kt, Theme.kt
          login/          # LoginScreen + LoginViewModel
          home/           # HomeScreen + HomeViewModel
          register/       # RegisterScreen + RegisterViewModel
          verify/         # VerifyScreen + VerifyViewModel
          service/        # ServiceScreen + ServiceViewModel
          printer/        # PrinterScreen + PrinterViewModel
          components/     # EnvelopeHero, DocRow, ScanTarget, Toast, BottomSheet, ...
        MainActivity.kt
        ConvertTrackApp.kt  # @HiltAndroidApp
      res/
        drawable/         # Lucide SVG иконки, logo-lockup.png, logo-icon.png
        font/             # Roboto-*.ttf, RobotoCondensed-*.ttf
        raw/
          scan_success.ogg  # позитивный бип — успешный скан
          scan_error.ogg    # двойной сигнал — ошибка скана
```

---

## 5. Навигация

```
LoginScreen
    └──► HomeScreen
              ├──► RegisterScreen  →  (HomeScreen после Готово)
              ├──► VerifyScreen    →  (HomeScreen после завершения)
              └──► ServiceScreen
                        └──► PrinterScreen
```

**Стартовая логика:** при запуске проверяем DataStore — если `serverUrl` и `operatorToken` существуют, переходим сразу на `HomeScreen`, иначе на `LoginScreen`.

---

## 6. Аутентификация

Существующий backend использует Cookie-аутентификацию (`operator_name` cookie, без пароля — только проверка что оператор активен в БД).

**Новый endpoint на backend (добавить в v1.2):** `POST /api/auth/login`
```json
// Request:  {"name": "Иванов"}
// Response: Set-Cookie: operator_name=<encoded>; HttpOnly; SameSite=Lax
//           {"ok": true, "operator": "Иванов"}
```

Логика Android:
- `LoginScreen` вызывает `POST /api/auth/login` с именем оператора
- OkHttp `CookieJar` автоматически сохраняет и отправляет `operator_name` cookie
- Имя оператора дополнительно сохраняется в DataStore (для отображения в UI)
- При получении `401/403` — выход: очистка DataStore + навигация на `LoginScreen`

**Конфигурация сервера:** URL вводится один раз на `ServiceScreen` и сохраняется в DataStore. При первом запуске (serverUrl пуст) показывается поле ввода URL перед логином.

---

## 7. Абстракция сканера

```kotlin
interface ScannerManager {
    val barcodes: Flow<String>
    fun start(context: Context)
    fun stop()
}

class UrovoScannerManager : ScannerManager {
    // BroadcastReceiver на "urovo.rcv.message", extra "barcodeStr"
}

class MindeoScannerManager : ScannerManager {
    // BroadcastReceiver на broadcast action Mindeo (уточнить на устройстве)
    // Fallback: аналогичная структура
}
```

Выбор реализации в Hilt-модуле по `Build.MANUFACTURER.lowercase()`:
- `"urovo"` → `UrovoScannerManager`
- `"mindeo"` → `MindeoScannerManager`
- иначе → `UrovoScannerManager` (fallback)

`ViewModel` подписывается на `scannerManager.barcodes: Flow<String>` и обрабатывает каждый штрихкод.

---

## 8. Состояние экранов

Каждый экран имеет один `StateFlow<UiState>` в ViewModel. Compose подписывается через `collectAsStateWithLifecycle()`.

Пример для RegisterScreen:
```kotlin
data class RegisterUiState(
    val envelope: Envelope? = null,
    val docs: List<Document> = emptyList(),
    val isSealed: Boolean = false,
    val isLoading: Boolean = false,
    val toast: ToastMessage? = null,
    val sheetOpen: Boolean = false
)
```

---

## 9. Печать

Существующие endpoints возвращают контент клиенту (используются веб-UI). Для TSD нужны новые backend endpoints (добавить в v1.2):

| Endpoint | Назначение |
|---|---|
| `GET /api/printers` | Список доступных ZPL-принтеров (из конфига backend) |
| `POST /api/envelopes/{id}/print/label/send?printer_id={id}` | Backend шлёт ZPL напрямую на принтер по TCP:9100 |
| `POST /api/envelopes/{id}/print/inventory/send?printer_id={id}` | Backend шлёт опись на A4-принтер через системную печать |

Логика Android:
- `PrinterScreen` загружает список принтеров через `GET /api/printers`
- Выбранный `printerId` сохраняется в DataStore
- После запечатывания: `POST .../print/label/send?printer_id={id}` — backend сам отправляет ZPL
- Ошибка принтера показывает Toast, но **не блокирует** завершение операции (конверт уже запечатан)

---

## 10. Обратная связь при сканировании

| Событие | Вибрация | Звук |
|---|---|---|
| Успешный скан | 50 мс | `scan_success.ogg` |
| Ошибка (неверный ШК / не из конверта) | 3×100 мс | `scan_error.ogg` |

Звуки хранятся в `res/raw/`, воспроизводятся через `SoundPool` (минимальная задержка).  
Замена звуков — только замена файлов, без изменения кода.

---

## 11. Обработка ошибок

| Ситуация | Поведение |
|---|---|
| Сервер недоступен | Toast «Сервер недоступен. Проверьте подключение» |
| ШК не является документом 1С | Toast «ШК не похож на штрихкод документа 1С» |
| Документ не из этого конверта | Toast красный «Документ не из этого конверта» |
| Документ уже в другом конверте | Toast «Документ уже в конверте ТА-XXXXXXXX» |
| 401 Unauthorized | Выход на LoginScreen + очистка токена |
| Принтер недоступен | Toast «Принтер не отвечает», операция продолжается |

---

## 12. Дизайн-система

Все цвета, типографика, отступы и компоненты берутся из `design/system/`.  
Токены переносятся в `ui/theme/Color.kt`, `Type.kt`, `Theme.kt`.  
HTML-прототип всех экранов: `design/system/ui_kits/tsd_android/index.html`.

---

## 13. Связанные документы

- `project-overview.md` — полная архитектура системы
- `design/system/README.md` — дизайн-хэндофф (цвета, типографика, компоненты)
- `design/system/ui_kits/tsd_android/index.html` — интерактивный прототип
- `docs/superpowers/specs/2026-04-26-konvert-trek-mvp-design.md` — MVP spec
- `docs/superpowers/specs/2026-04-30-v1.1-design.md` — v1.1 spec
