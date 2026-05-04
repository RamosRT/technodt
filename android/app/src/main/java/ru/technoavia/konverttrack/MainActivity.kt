package ru.technoavia.konverttrack

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.MediaPlayer
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.json.JSONObject
import retrofit2.HttpException
import ru.technoavia.konverttrack.data.api.ApiClient
import ru.technoavia.konverttrack.data.api.DocumentAddRequest
import ru.technoavia.konverttrack.data.api.EnvelopeDto
import ru.technoavia.konverttrack.data.api.LoginRequest
import ru.technoavia.konverttrack.data.api.PrinterDto
import ru.technoavia.konverttrack.data.api.SealRequest
import ru.technoavia.konverttrack.data.api.VerifyFinishRequest
import ru.technoavia.konverttrack.data.api.VerifyScanRequest
import ru.technoavia.konverttrack.ui.theme.BrandBlue
import ru.technoavia.konverttrack.ui.theme.BrandBlueMidStop
import ru.technoavia.konverttrack.ui.theme.BrandBlueLight
import ru.technoavia.konverttrack.ui.theme.BrandBlueMid
import ru.technoavia.konverttrack.ui.theme.BrandRed
import ru.technoavia.konverttrack.ui.theme.BrandGreen
import ru.technoavia.konverttrack.ui.theme.BrandInk
import ru.technoavia.konverttrack.ui.theme.BorderLine
import ru.technoavia.konverttrack.ui.theme.BorderSoft
import ru.technoavia.konverttrack.ui.theme.DangerBg
import ru.technoavia.konverttrack.ui.theme.FgLabel
import ru.technoavia.konverttrack.ui.theme.FgMuted
import ru.technoavia.konverttrack.ui.theme.SuccessBg
import ru.technoavia.konverttrack.ui.theme.SuccessGreen
import ru.technoavia.konverttrack.ui.theme.SurfaceAlt
import ru.technoavia.konverttrack.ui.theme.SurfaceTint
import ru.technoavia.konverttrack.ui.theme.WarningBg
import ru.technoavia.konverttrack.ui.theme.WarningOrange
import ru.technoavia.konverttrack.ui.theme.KonvertTrackTheme
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

class MainActivity : ComponentActivity() {
    private var openServiceMenu: (() -> Unit)? = null
    private var handleBarcode: ((String) -> Unit)? = null
    private var sealEnvelope: (() -> Unit)? = null
    private val scannerReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action !in SCAN_ACTIONS) return

            val barcode = intent.extractBarcode()
            Log.d(TAG, "Scanner broadcast action=${intent.action} extras=${intent.extras?.keySet()?.joinToString()}")
            if (!barcode.isNullOrBlank()) {
                Log.d(TAG, "Scanner barcode received rawLength=${barcode.length} normalizedLength=${barcode.normalizeBarcode().length}")
                handleBarcode?.invoke(barcode)
            } else {
                Log.w(TAG, "Scanner broadcast without barcode string")
            }
        }
    }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(
            android.view.WindowManager.LayoutParams.FLAG_FULLSCREEN,
            android.view.WindowManager.LayoutParams.FLAG_FULLSCREEN,
        )
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.decorView.post {
            WindowInsetsControllerCompat(window, window.decorView).apply {
                hide(WindowInsetsCompat.Type.systemBars())
                systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        }
        val prefs = getSharedPreferences("konvert_track", Context.MODE_PRIVATE)
        val scannerFilter = IntentFilter().apply {
            SCAN_ACTIONS.forEach { addAction(it) }
        }
        registerReceiver(scannerReceiver, scannerFilter)
        setContent {
            KonvertTrackTheme {
                AppRoot(
                    savedServerUrl = prefs.getString("server_url", "") ?: "",
                    onSaveLogin = { serverUrl, operator, assignedPrinterId ->
                        val edit = prefs.edit()
                            .putString("server_url", serverUrl)
                            .putString("operator", operator)
                        if (!assignedPrinterId.isNullOrBlank()) {
                            edit.putString("printer_id", assignedPrinterId)
                        }
                        edit.apply()
                    },
                    onClearLogin = {
                        prefs.edit().remove("operator").apply()
                    },
                    loadPreference = { key -> prefs.getString(key, "") ?: "" },
                    savePreference = { key, value -> prefs.edit().putString(key, value).apply() },
                    bindServiceMenu = { callback -> openServiceMenu = callback },
                    bindBarcode = { callback -> handleBarcode = callback },
                    bindSealEnvelope = { callback -> sealEnvelope = callback },
                )
            }
        }
    }

    override fun onDestroy() {
        unregisterReceiver(scannerReceiver)
        super.onDestroy()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_F4) {
            openServiceMenu?.invoke()
            return true
        }
        if (keyCode == KeyEvent.KEYCODE_F1) {
            sealEnvelope?.invoke()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun Intent.extractBarcode(): String? {
        val preferredKeys = listOf(
            "barcodeStr",
            "barcode_string",
            "barcode",
            "barocode",
            "scannerdata",
            "data",
            "value",
        )
        for (key in preferredKeys) {
            getStringExtra(key)?.let { return it.trim() }
        }
        val bundle = extras ?: return null
        return bundle.keySet()
            .asSequence()
            .mapNotNull { key -> bundle.get(key) as? String }
            .firstOrNull { it.isNotBlank() }
            ?.trim()
    }

    private companion object {
        const val TAG = "KonvertTrack"
        const val UROVO_SCAN_ACTION = "urovo.rcv.message"
        const val UROVO_DECODE_ACTION = "android.intent.ACTION_DECODE_DATA"
        val SCAN_ACTIONS = setOf(UROVO_SCAN_ACTION, UROVO_DECODE_ACTION)
    }
}

private fun String.normalizeBarcode(): String {
    val withoutAim = stripScannerServicePrefix()
    return withoutAim.filter { it.isDigit() }
}

private fun String.stripScannerServicePrefix(): String {
    val cleaned = replace('\u0000', ' ').trim()
    return if (
        cleaned.length >= 3 &&
        cleaned[0] == ']' &&
        cleaned[1].isLetter() &&
        cleaned[2].isDigit()
    ) {
        cleaned.substring(3).trim()
    } else {
        cleaned
    }
}

private fun String.toDisplayDate(): String {
    val parts = split("-")
    return if (parts.size == 3) "${parts[2]}.${parts[1]}.${parts[0]}" else this
}

@Composable
private fun AppRoot(
    savedServerUrl: String,
    onSaveLogin: (String, String, String?) -> Unit,
    onClearLogin: () -> Unit,
    loadPreference: (String) -> String,
    savePreference: (String, String) -> Unit,
    bindServiceMenu: ((() -> Unit)?) -> Unit,
    bindBarcode: (((String) -> Unit)?) -> Unit,
    bindSealEnvelope: ((() -> Unit)?) -> Unit,
) {
    var operator by rememberSaveable { mutableStateOf<String?>(null) }
    var online by rememberSaveable { mutableStateOf(false) }
    var screen by rememberSaveable { mutableStateOf("home") }
    var currentServerUrl by rememberSaveable { mutableStateOf(savedServerUrl) }
    var branch by rememberSaveable { mutableStateOf(loadPreference("branch")) }
    var branchId by rememberSaveable { mutableStateOf(loadPreference("branch_id")) }
    var signer by rememberSaveable { mutableStateOf(loadPreference("signer")) }
    var signerId by rememberSaveable { mutableStateOf(loadPreference("signer_id")) }
    var printer by rememberSaveable { mutableStateOf(loadPreference("printer")) }
    var printerId by rememberSaveable { mutableStateOf(loadPreference("printer_id")) }
    var currentEnvelope by remember { mutableStateOf<EnvelopeDto?>(null) }
    var verifyEnvelope by remember { mutableStateOf<EnvelopeDto?>(null) }
    var registerMessage by remember { mutableStateOf<String?>(null) }
    var registerError by remember { mutableStateOf<String?>(null) }
    var verifyMessage by remember { mutableStateOf<String?>(null) }
    var verifyError by remember { mutableStateOf<String?>(null) }
    var showLogoutConfirm by rememberSaveable { mutableStateOf(false) }
    var showRegisterExitConfirm by rememberSaveable { mutableStateOf(false) }
    var showVerifyForceFinishConfirm by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    fun returnFromRegisterToHome() {
        registerMessage = null
        registerError = null
        currentEnvelope = null
        screen = "home"
    }

    fun performLogout() {
        ApiClient.clearCookies()
        onClearLogin()
        operator = null
        online = false
        screen = "home"
        currentEnvelope = null
        registerMessage = null
        registerError = null
        verifyEnvelope = null
        verifyMessage = null
        verifyError = null
    }

    LaunchedEffect(operator, screen) {
        bindServiceMenu(
            if (operator != null && screen == "home") {
                { screen = "service" }
            } else {
                null
            },
        )
    }

    LaunchedEffect(screen, currentEnvelope?.status) {
        bindSealEnvelope(null)
    }

    LaunchedEffect(screen, currentServerUrl, currentEnvelope?.id, verifyEnvelope?.id) {
        bindBarcode(
            when {
                screen == "register" && currentEnvelope != null -> { rawBarcode ->
                    val envelopeId = currentEnvelope?.id
                    if (envelopeId != null) {
                        val raw = rawBarcode.stripScannerServicePrefix()
                        val barcode = rawBarcode.normalizeBarcode()
                        scope.launch {
                            registerMessage = null
                            registerError = null
                            val api = ApiClient.envelopeApi(currentServerUrl)

                            val envelopeCandidates = listOf(raw, barcode)
                                .map { it.trim() }
                                .filter { it.isNotBlank() }
                                .distinct()
                            var scannedEnvelope: EnvelopeDto? = null
                            for (candidate in envelopeCandidates) {
                                val found = runCatching {
                                    api.getByBarcode(candidate)
                                }.getOrNull()
                                if (found != null) {
                                    scannedEnvelope = found
                                    break
                                }
                            }

                            if (scannedEnvelope != null) {
                                when (scannedEnvelope.status) {
                                    "draft" -> {
                                        if (scannedEnvelope.id != envelopeId) {
                                            currentEnvelope = scannedEnvelope
                                            registerMessage = "Открыт черновик: ${scannedEnvelope.number}"
                                        } else {
                                            registerMessage = "Текущий черновик уже открыт"
                                        }
                                        playScanSound(context, success = true)
                                        return@launch
                                    }
                                    "sealed" -> {
                                        registerError = "Конверт уже запечатан, дозаполнение невозможно"
                                        playScanSound(context, success = false)
                                        return@launch
                                    }
                                    else -> {
                                        registerError = "Конверт в статусе ${scannedEnvelope.status}, дозаполнение недоступно"
                                        playScanSound(context, success = false)
                                        return@launch
                                    }
                                }
                            }

                            if (barcode.isBlank()) {
                                registerError = "ШК не содержит цифр"
                                playScanSound(context, success = false)
                                return@launch
                            }
                            runCatching {
                                api.addDocument(envelopeId, DocumentAddRequest(barcode))
                            }.onSuccess { doc ->
                                val envelope = currentEnvelope
                                if (envelope != null && envelope.documents.none { it.id == doc.id }) {
                                    currentEnvelope = envelope.copy(documents = envelope.documents + doc)
                                }
                                registerMessage = "Документ добавлен: ${doc.doc_number}"
                                playScanSound(context, success = true)
                            }.onFailure { error ->
                                registerError = apiErrorText(error)
                                playScanSound(context, success = false)
                            }
                        }
                    }
                }
                screen == "verify_start" -> { rawBarcode ->
                    val barcode = rawBarcode.normalizeBarcode()
                    scope.launch {
                        verifyMessage = null
                        verifyError = null
                        if (barcode.isBlank()) {
                            verifyError = "ШК конверта не распознан"
                            return@launch
                        }
                        runCatching {
                            val api = ApiClient.envelopeApi(currentServerUrl)
                            val envelope = api.getByBarcode(barcode)
                            val started = api.verifyStart(envelope.id)
                            started
                        }.onSuccess { started ->
                            verifyEnvelope = started
                            verifyMessage = "Конверт найден: ${started.number}"
                            screen = "verify"
                        }.onFailure { err ->
                            verifyError = apiErrorText(err)
                        }
                    }
                }
                screen == "verify" && verifyEnvelope != null -> { rawBarcode ->
                    val envelopeId = verifyEnvelope?.id
                    if (envelopeId != null) {
                        val barcode = rawBarcode.normalizeBarcode()
                        scope.launch {
                            verifyMessage = null
                            verifyError = null
                            if (barcode.isBlank()) {
                                verifyError = "ШК документа не распознан"
                                return@launch
                            }
                            runCatching {
                                val api = ApiClient.envelopeApi(currentServerUrl)
                                val scan = api.verifyScan(envelopeId, VerifyScanRequest(barcode))
                                val fresh = api.getByBarcode(verifyEnvelope?.barcode.orEmpty())
                                scan to fresh
                            }.onSuccess { (scan, fresh) ->
                                verifyEnvelope = fresh
                                when {
                                    !scan.matched -> {
                                        verifyError = "Документ не найден в составе этого конверта"
                                        playScanSound(context, success = false)
                                    }
                                    scan.reason == "already_scanned" -> {
                                        verifyMessage = "Документ уже был отсканирован ранее"
                                        playScanSound(context, success = false)
                                    }
                                    else -> {
                                        verifyMessage = "Документ отсканирован"
                                        playScanSound(context, success = true)
                                    }
                                }
                            }.onFailure { err ->
                                verifyError = apiErrorText(err)
                                playScanSound(context, success = false)
                            }
                        }
                    }
                }
                else -> null
            },
        )
    }

    if (operator != null) {
        BackHandler {
            when (screen) {
                "home" -> showLogoutConfirm = true
                "service" -> screen = "home"
                "register" -> {
                    val docsCount = currentEnvelope?.documents?.size ?: 0
                    if (docsCount > 1) {
                        showRegisterExitConfirm = true
                    } else {
                        returnFromRegisterToHome()
                    }
                }
                "verify_start", "verify" -> {
                    verifyEnvelope = null
                    verifyMessage = null
                    verifyError = null
                    screen = "home"
                }
                else -> screen = "home"
            }
        }
    }

    if (showLogoutConfirm) {
        AlertDialog(
            onDismissRequest = { showLogoutConfirm = false },
            title = { Text("Выход из аккаунта") },
            text = { Text("Вы действительно хотите выйти?") },
            confirmButton = {
                Button(
                    onClick = {
                        showLogoutConfirm = false
                        performLogout()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandRed),
                ) {
                    Text("Выйти")
                }
            },
            dismissButton = {
                Button(
                    onClick = { showLogoutConfirm = false },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Отмена")
                }
            },
        )
    }

    if (showRegisterExitConfirm) {
        AlertDialog(
            onDismissRequest = { showRegisterExitConfirm = false },
            title = { Text("Вернуться на главный экран") },
            text = { Text("Уже отсканировано больше одного документа. Выйти на главный экран? Черновик будет сохранен.") },
            confirmButton = {
                Button(
                    onClick = {
                        showRegisterExitConfirm = false
                        returnFromRegisterToHome()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandRed),
                ) {
                    Text("Выйти")
                }
            },
            dismissButton = {
                Button(
                    onClick = { showRegisterExitConfirm = false },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Остаться")
                }
            },
        )
    }

    if (showVerifyForceFinishConfirm) {
        AlertDialog(
            onDismissRequest = { showVerifyForceFinishConfirm = false },
            title = { Text("Завершить с расхождением") },
            text = { Text("Не все документы отсканированы. Завершить сверку с расхождением?") },
            confirmButton = {
                Button(
                    onClick = {
                        val envelopeId = verifyEnvelope?.id
                        if (envelopeId == null) {
                            showVerifyForceFinishConfirm = false
                            return@Button
                        }
                        scope.launch {
                            showVerifyForceFinishConfirm = false
                            verifyMessage = null
                            verifyError = null
                            runCatching {
                                ApiClient.envelopeApi(currentServerUrl).verifyFinish(envelopeId, VerifyFinishRequest(force = true))
                            }.onSuccess {
                                verifyMessage = "Сверка завершена с расхождением"
                                verifyEnvelope = null
                                screen = "home"
                            }.onFailure { err ->
                                verifyError = apiErrorText(err)
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandRed),
                ) { Text("Завершить") }
            },
            dismissButton = {
                Button(
                    onClick = { showVerifyForceFinishConfirm = false },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) { Text("Отмена") }
            },
        )
    }

    if (operator == null) {
        LoginScreen(
            savedServerUrl = savedServerUrl,
            bindServiceMenu = bindServiceMenu,
            bindBarcode = bindBarcode,
            onLoginSuccess = { serverUrl, name, assignedPrinterId ->
                onSaveLogin(serverUrl, name, assignedPrinterId)
                currentServerUrl = serverUrl
                if (!assignedPrinterId.isNullOrBlank()) {
                    printerId = assignedPrinterId
                    savePreference("printer_id", assignedPrinterId)
                }
                operator = name
                online = true
                screen = "home"
            },
        )
    } else if (screen == "service") {
        ServiceScreen(
            operator = operator.orEmpty(),
            serverUrl = currentServerUrl,
            isOnline = online,
            branch = branch,
            branchId = branchId,
            signer = signer,
            signerId = signerId,
            printer = printer,
            printerId = printerId,
            onBack = { screen = "home" },
            onSaveSettings = { server, selectedBranchId, newBranch, selectedSignerId, newSigner, selectedPrinterId, newPrinter ->
                currentServerUrl = server
                branchId = selectedBranchId
                branch = newBranch
                signerId = selectedSignerId
                signer = newSigner
                printerId = selectedPrinterId
                printer = newPrinter
                savePreference("server_url", server)
                savePreference("branch_id", selectedBranchId)
                savePreference("branch", newBranch)
                savePreference("signer_id", selectedSignerId)
                savePreference("signer", newSigner)
                savePreference("printer_id", selectedPrinterId)
                savePreference("printer", newPrinter)
                screen = "home"
            },
            onLogout = {
                performLogout()
            },
        )
    } else if (screen == "register" && currentEnvelope != null) {
        RegisterScreen(
            envelope = currentEnvelope!!,
            serverUrl = currentServerUrl,
            isOnline = online,
            message = registerMessage,
            error = registerError,
            branchId = branchId,
            signerId = signerId,
            printerId = printerId,
            onEnvelopeChanged = { envelope -> currentEnvelope = envelope },
            bindSealEnvelope = bindSealEnvelope,
            onBack = {
                val docsCount = currentEnvelope?.documents?.size ?: 0
                if (docsCount > 1) {
                    showRegisterExitConfirm = true
                } else {
                    returnFromRegisterToHome()
                }
            },
            onDone = {
                registerMessage = null
                registerError = null
                currentEnvelope = null
                screen = "home"
            },
        )
    } else if (screen == "verify_start") {
        VerifyStartScreen(
            isOnline = online,
            message = verifyMessage,
            error = verifyError,
            onBack = { screen = "home" },
        )
    } else if (screen == "verify" && verifyEnvelope != null) {
        VerifyScreen(
            envelope = verifyEnvelope!!,
            isOnline = online,
            message = verifyMessage,
            error = verifyError,
            onBack = {
                verifyEnvelope = null
                verifyMessage = null
                verifyError = null
                screen = "home"
            },
            onFinish = {
                val envelopeId = verifyEnvelope?.id ?: return@VerifyScreen
                scope.launch {
                    verifyMessage = null
                    verifyError = null
                    runCatching {
                        ApiClient.envelopeApi(currentServerUrl).verifyFinish(envelopeId, VerifyFinishRequest(force = false))
                    }.onSuccess {
                        verifyMessage = "Сверка завершена"
                        verifyEnvelope = null
                        screen = "home"
                    }.onFailure { err ->
                        if (err is HttpException && err.code() == 409) {
                            showVerifyForceFinishConfirm = true
                        } else {
                            verifyError = apiErrorText(err)
                        }
                    }
                }
            },
        )
    } else {
        TsdShell(
            operator = operator.orEmpty(),
            serverUrl = currentServerUrl,
            isOnline = online,
            onOpenService = { screen = "service" },
            onOpenVerify = {
                verifyEnvelope = null
                verifyMessage = null
                verifyError = null
                screen = "verify_start"
            },
            onEnvelopeCreated = { envelope ->
                registerMessage = null
                registerError = null
                currentEnvelope = envelope
                screen = "register"
            },
        )
    }
}

@Composable
private fun LoginScreen(
    savedServerUrl: String,
    bindServiceMenu: ((() -> Unit)?) -> Unit,
    bindBarcode: (((String) -> Unit)?) -> Unit,
    onLoginSuccess: (String, String, String?) -> Unit,
) {
    var serverUrl by rememberSaveable { mutableStateOf(savedServerUrl) }
    var username by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var logoTapCount by rememberSaveable { mutableStateOf(0) }
    var showServerDialog by rememberSaveable { mutableStateOf(savedServerUrl.isBlank()) }
    var isLoading by remember { mutableStateOf(false) }
    var errorText by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun submitLogin(nextServerUrl: String = serverUrl, nextUsername: String = username, nextPassword: String = password) {
        scope.launch {
            isLoading = true
            errorText = null
            runCatching {
                ApiClient.authApi(nextServerUrl).login(LoginRequest(nextUsername.trim(), nextPassword))
            }.onSuccess { response ->
                if (response.ok) {
                    onLoginSuccess(nextServerUrl.trim(), response.operator, response.assigned_zpl_printer_id)
                } else {
                    errorText = "Вход не выполнен"
                }
            }.onFailure { error ->
                errorText = loginErrorText(error)
            }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        bindServiceMenu { showServerDialog = true }
    }

    LaunchedEffect(serverUrl) {
        bindBarcode { rawBarcode ->
            val qr = parseLoginQr(rawBarcode)
            if (qr == null) {
                errorText = "QR входа не распознан"
            } else {
                serverUrl = qr.serverUrl
                username = qr.username
                password = qr.password
                submitLogin(qr.serverUrl, qr.username, qr.password)
            }
        }
    }

    if (showServerDialog) {
        ServerUrlDialog(
            serverUrl = serverUrl,
            onServerUrlChange = {
                serverUrl = it
                errorText = null
            },
            onDismiss = { showServerDialog = false },
        )
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 22.dp),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                Image(
                    painter = painterResource(R.drawable.logo_lockup),
                    contentDescription = "ТехноКонверт",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(84.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .clickable {
                            logoTapCount += 1
                            if (logoTapCount >= 5) {
                                logoTapCount = 0
                                showServerDialog = true
                            }
                        },
                    contentScale = ContentScale.Fit,
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    "Учёт передачи документов · ТСД",
                    style = MaterialTheme.typography.labelSmall,
                    color = FgMuted,
                )
                Spacer(modifier = Modifier.height(28.dp))
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Имя оператора".uppercase(), style = MaterialTheme.typography.labelSmall, color = FgLabel, letterSpacing = 0.5.sp)
                        OutlinedTextField(
                            value = username,
                            onValueChange = {
                                username = it
                                errorText = null
                            },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            placeholder = { Text("ivan.petrov") },
                            shape = RoundedCornerShape(8.dp),
                        )
                    }
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("PIN-код".uppercase(), style = MaterialTheme.typography.labelSmall, color = FgLabel, letterSpacing = 0.5.sp)
                        OutlinedTextField(
                            value = password,
                            onValueChange = {
                                password = it.filter(Char::isDigit).take(4)
                                errorText = null
                            },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            placeholder = { Text("••••") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                            visualTransformation = PasswordVisualTransformation(),
                            shape = RoundedCornerShape(8.dp),
                        )
                    }
                    if (errorText != null) {
                        ScanFeedbackBanner(errorText, isError = true)
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color.White)
                        .border(1.dp, BorderSoft, RoundedCornerShape(8.dp))
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Box(modifier = Modifier.size(8.dp).clip(CircleShape).background(if (serverUrl.isNotBlank()) SuccessGreen else BrandRed))
                    Text(
                        text = if (serverUrl.isNotBlank()) "Сервер: $serverUrl" else "Адрес сервера не задан",
                        style = MaterialTheme.typography.labelSmall,
                        color = FgMuted,
                    )
                }
            }
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Button(
                    onClick = { submitLogin() },
                    enabled = !isLoading && serverUrl.isNotBlank() && username.isNotBlank() && password.length == 4,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                    } else {
                        Text("Войти", style = MaterialTheme.typography.titleMedium)
                    }
                }
                Text("v1.2.0 · build 1", style = MaterialTheme.typography.labelSmall, color = FgLabel)
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}

private fun loginErrorText(error: Throwable): String {
    return when (error) {
        is IllegalArgumentException -> "Некорректный адрес сервера"
        is HttpException -> when (error.code()) {
            401, 403 -> "Неверный логин или код"
            else -> "Сервер вернул ошибку ${error.code()}"
        }
        else -> "Сервер недоступен. Проверьте подключение"
    }
}

private data class LoginQrPayload(
    val serverUrl: String,
    val username: String,
    val password: String,
)

private data class LoginCandidate(
    val server: String? = null,
    val username: String? = null,
    val pin: String? = null,
)

private fun String.parseCandidateTokens(): LoginCandidate {
    val candidate = this.trim()
    if (candidate.isBlank()) return LoginCandidate()
    if (candidate.contains("=") && !candidate.contains("|")) {
        val kv = candidate
            .split("&", ";", "\n")
            .mapNotNull { token ->
                val idx = token.indexOf('=')
                if (idx <= 0 || idx >= token.lastIndex) {
                    null
                } else {
                    val key = token.substring(0, idx).trim().lowercase()
                    val value = token.substring(idx + 1).trim()
                    key to value
                }
            }.toMap()
        return LoginCandidate(
            server = kv["server"] ?: kv["server_url"] ?: kv["url"] ?: kv["host"],
            username = kv["username"] ?: kv["user"] ?: kv["operator"] ?: kv["login"],
            pin = kv["pin"] ?: kv["password"] ?: kv["code"],
        )
    }

    val parts = candidate.split("|").map { it.trim() }
    return if (parts.size == 4) {
        LoginCandidate(server = parts[1], username = parts[2], pin = parts[3])
    } else {
        LoginCandidate()
    }
}

private fun parseLoginQr(raw: String): LoginQrPayload? {
    val trimmed = raw.trim()
    val withoutAim = if (
        trimmed.length >= 3 &&
        trimmed[0] == ']' &&
        trimmed[1].isLetter() &&
        trimmed[2].isDigit()
    ) {
        trimmed.substring(3)
    } else {
        trimmed
    }

    val normalized = withoutAim.replace('\u0000', ' ').trim()
    val direct = normalized.split("|").map { it.trim() }
    val isLegacyKtLogin = direct.size == 4 && direct[0].equals("KTLOGIN", ignoreCase = true)
    val legacyCandidate = if (isLegacyKtLogin) {
        LoginCandidate(server = direct[1], username = direct[2], pin = direct[3])
    } else {
        LoginCandidate()
    }

    val uriCandidate = if (normalized.startsWith("ktlogin://", ignoreCase = true)) {
        runCatching {
            val query = normalized.substringAfter('?', "")
            URLDecoder.decode(query, StandardCharsets.UTF_8).parseCandidateTokens()
        }.getOrDefault(LoginCandidate())
    } else {
        LoginCandidate()
    }

    val keyValueCandidate = normalized.parseCandidateTokens()
    val picked = when {
        !legacyCandidate.server.isNullOrBlank() -> legacyCandidate
        !uriCandidate.server.isNullOrBlank() -> uriCandidate
        else -> keyValueCandidate
    }

    val pin = picked.pin?.trim().orEmpty()
    val username = picked.username?.trim().orEmpty()
    val server = picked.server?.trim().orEmpty()
    if (server.isBlank() || username.isBlank() || pin.length != 4 || !pin.all(Char::isDigit)) {
        return null
    }
    return LoginQrPayload(server, username, pin)
}

@Composable
private fun ServerUrlDialog(
    serverUrl: String,
    onServerUrlChange: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Адрес сервера") },
        text = {
            OutlinedTextField(
                value = serverUrl,
                onValueChange = onServerUrlChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("http://192.168.1.10:8080") },
            )
        },
        confirmButton = {
            Button(
                onClick = onDismiss,
                enabled = serverUrl.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
            ) {
                Text("Сохранить")
            }
        },
    )
}

private fun apiErrorText(error: Throwable): String {
    if (error is HttpException) {
        val body = error.response()?.errorBody()?.string()
        val detail = runCatching {
            body?.let { JSONObject(it).optString("detail").takeIf(String::isNotBlank) }
        }.getOrNull()
        if (!detail.isNullOrBlank()) return detail
    }
    return loginErrorText(error)
}

private fun playScanSound(context: Context, success: Boolean) {
    val resId = if (success) R.raw.applepay else R.raw.oshibka_windows_xp
    runCatching {
        MediaPlayer.create(context, resId)?.apply {
            setOnCompletionListener { player -> player.release() }
            setOnErrorListener { player, _, _ ->
                player.release()
                true
            }
            start()
        }
    }
}

@Composable
private fun TsdShell(
    operator: String,
    serverUrl: String,
    isOnline: Boolean,
    onOpenService: () -> Unit,
    onOpenVerify: () -> Unit,
    onEnvelopeCreated: (EnvelopeDto) -> Unit,
) {
    var isCreatingEnvelope by remember { mutableStateOf(false) }
    var createError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            TopBar(operator = operator, onOpenService = onOpenService)
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                SectionLabel("Действия")
                ActionGrid(
                    isCreatingEnvelope = isCreatingEnvelope,
                    onCreateEnvelope = {
                        scope.launch {
                            isCreatingEnvelope = true
                            createError = null
                            runCatching {
                                ApiClient.envelopeApi(serverUrl).createEnvelope()
                            }.onSuccess { envelope ->
                                onEnvelopeCreated(envelope)
                            }.onFailure { error ->
                                createError = loginErrorText(error)
                            }
                            isCreatingEnvelope = false
                        }
                    },
                    onOpenVerify = onOpenVerify,
                )
                if (createError != null) {
                    Text(createError.orEmpty(), color = BrandRed, style = MaterialTheme.typography.labelSmall)
                }
                SectionLabel("Последние")
                RecentEnvelopeStub()
            }
            ConnBanner(isOnline = isOnline)
        }
    }
}

@Composable
private fun RegisterScreen(
    envelope: EnvelopeDto,
    serverUrl: String,
    isOnline: Boolean,
    message: String?,
    error: String?,
    branchId: String,
    signerId: String,
    printerId: String,
    onEnvelopeChanged: (EnvelopeDto) -> Unit,
    bindSealEnvelope: ((() -> Unit)?) -> Unit,
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    var sealMessage by remember { mutableStateOf<String?>(null) }
    var sealError by remember { mutableStateOf<String?>(null) }
    var isSealing by remember { mutableStateOf(false) }
    var printMessage by remember { mutableStateOf<String?>(null) }
    var printError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
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

    LaunchedEffect(envelope.status, envelope.documents.size, branchId, signerId) {
        bindSealEnvelope(
            if (envelope.status != "sealed") {
                sealAction
            } else {
                null
            },
        )
    }

    val sealed = envelope.status == "sealed"
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            RegisterTopBar(
                onBack = onBack,
                title = if (sealed) "Регистрация" else "Новый конверт",
                subtitle = if (sealed) "Конверт запечатан" else "Сканируйте документы",
            )
            EnvelopeHero(envelope)
            if (sealed) {
                SealedEnvelopeScreen(
                    envelope = envelope,
                    printMessage = printMessage,
                    printError = printError,
                    onPrint = {
                        if (printerId.isBlank()) {
                            printError = "Выберите ZPL-принтер в сервисном меню"
                        } else {
                            scope.launch {
                                printMessage = null
                                printError = null
                                runCatching {
                                    ApiClient.envelopeApi(serverUrl).printLabel(envelope.id, printerId)
                                }.onSuccess {
                                    printMessage = "Этикетка отправлена на принтер"
                                }.onFailure { err ->
                                    printError = apiErrorText(err)
                                }
                            }
                        }
                    },
                    onDone = onDone,
                    modifier = Modifier.weight(1f),
                )
            } else {
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState()),
                ) {
                    ScanTarget(
                        label = "Готов к сканированию",
                        hint = "${envelope.documents.size} в конверте · сканируйте следующий",
                        armed = true,
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    if (message != null || sealMessage != null) {
                        Box(modifier = Modifier.padding(horizontal = 14.dp)) {
                            ScanFeedbackBanner(message ?: sealMessage, isError = false)
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                    if (error != null || sealError != null) {
                        Box(modifier = Modifier.padding(horizontal = 14.dp)) {
                            ScanFeedbackBanner(error ?: sealError, isError = true)
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        SectionLabel("Документы в конверте")
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                            .background(Color.White)
                            .padding(horizontal = 0.dp),
                    ) {
                        if (envelope.documents.isEmpty()) {
                            EmptyRegisterState()
                        } else {
                            envelope.documents.forEachIndexed { i, doc ->
                                if (i > 0) {
                                    Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(BorderLine))
                                }
                                DocRow(
                                    index = i + 1,
                                    kind = doc.doc_kind,
                                    number = doc.doc_number,
                                    date = doc.doc_date.toDisplayDate(),
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(14.dp))
                }
                BottomBar {
                    Button(
                        onClick = onBack,
                        modifier = Modifier.size(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                        border = BorderStroke(1.dp, BorderSoft),
                        elevation = ButtonDefaults.buttonElevation(0.dp),
                        contentPadding = PaddingValues(0.dp),
                    ) {
                        Icon(
                            painter = painterResource(R.drawable.ic_arrow_left),
                            contentDescription = "Назад",
                            tint = FgMuted,
                        )
                    }
                    Button(
                        onClick = sealAction,
                        enabled = !isSealing && canSeal,
                        modifier = Modifier.weight(1f).height(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                    ) {
                        if (isSealing) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                        } else {
                            Text("Запечатать", style = MaterialTheme.typography.titleMedium)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RegisterTopBar(onBack: () -> Unit, title: String, subtitle: String? = null) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .background(GradBlue)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(44.dp)) {
            Icon(
                painter = painterResource(R.drawable.ic_arrow_left),
                contentDescription = "Назад",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onPrimary,
                style = MaterialTheme.typography.titleMedium,
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.65f),
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
    }
}

@Composable
private fun SealedEnvelopeScreen(
    envelope: EnvelopeDto,
    printMessage: String?,
    printError: String?,
    onPrint: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (printMessage != null) ScanFeedbackBanner(printMessage, isError = false)
            if (printError != null) ScanFeedbackBanner(printError, isError = true)
            SectionLabel("Печать")
            Button(
                onClick = onPrint,
                modifier = Modifier.fillMaxWidth().height(44.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = SurfaceTint),
                elevation = ButtonDefaults.buttonElevation(0.dp),
                border = BorderStroke(1.dp, Color(0xFFC9DEF0)),
            ) {
                Text("Этикетка ZPL", style = MaterialTheme.typography.bodyMedium, color = BrandBlue)
            }
            SectionLabel("Состав конверта")
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                    .background(Color.White),
            ) {
                envelope.documents.forEachIndexed { i, doc ->
                    if (i > 0) Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(BorderLine))
                    DocRow(i + 1, doc.doc_kind, doc.doc_number, doc.doc_date.toDisplayDate())
                }
            }
        }
        BottomBar {
            Button(
                onClick = onDone,
                modifier = Modifier.weight(1f).height(56.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = SuccessGreen),
            ) {
                Text("Готово", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable
private fun EnvelopeHero(envelope: EnvelopeDto) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(GradBlue)
            .padding(16.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                StatusPill(status = envelope.status, onDark = true)
                Spacer(modifier = Modifier.weight(1f))
                Text(
                    "Code128",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.55f),
                )
            }
            Text(
                envelope.number,
                color = MaterialTheme.colorScheme.onPrimary,
                style = MaterialTheme.typography.titleLarge,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Column {
                    Text(
                        "${envelope.documents.size}",
                        color = MaterialTheme.colorScheme.onPrimary,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "документов",
                        color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.65f),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun VerifyEnvelopeHero(
    envelopeNumber: String,
    status: String,
    scannedCount: Int,
    totalCount: Int,
    allScanned: Boolean,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(GradBlue)
            .padding(16.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(status = status, onDark = true)
                Spacer(modifier = Modifier.weight(1f))
            }
            Text(envelopeNumber, color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.titleLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Column {
                    Text(
                        "$scannedCount/$totalCount",
                        color = if (allScanned) BrandGreen else MaterialTheme.colorScheme.onPrimary,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "отсканировано",
                        color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.65f),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun EmptyRegisterState() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(SurfaceAlt),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_package_plus),
                contentDescription = null,
                tint = FgLabel,
                modifier = Modifier.size(26.dp),
            )
        }
        Text("Конверт пуст", style = MaterialTheme.typography.titleMedium, color = BrandInk)
        Text("Отсканируйте первый документ", style = MaterialTheme.typography.labelSmall, color = FgMuted)
    }
}

@Composable
private fun TopBar(operator: String, onOpenService: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .background(GradBlue)
            .padding(start = 4.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "ТехноКонверт",
                color = MaterialTheme.colorScheme.onPrimary,
                style = MaterialTheme.typography.titleMedium,
            )
            if (operator.isNotBlank()) {
                Text(
                    operator,
                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.65f),
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
        IconButton(
            onClick = onOpenService,
            modifier = Modifier.size(44.dp),
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_settings),
                contentDescription = "Сервисное меню",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
    }
}

@Composable
private fun ServiceScreen(
    operator: String,
    serverUrl: String,
    isOnline: Boolean,
    branch: String,
    branchId: String,
    signer: String,
    signerId: String,
    printer: String,
    printerId: String,
    onBack: () -> Unit,
    onSaveSettings: (String, String, String, String, String, String, String) -> Unit,
    onLogout: () -> Unit,
) {
    var editableServerUrl by rememberSaveable(serverUrl) { mutableStateOf(serverUrl) }
    var editableBranch by rememberSaveable(branch) { mutableStateOf(branch) }
    var editableBranchId by rememberSaveable(branchId) { mutableStateOf(branchId) }
    var editableSigner by rememberSaveable(signer) { mutableStateOf(signer) }
    var editableSignerId by rememberSaveable(signerId) { mutableStateOf(signerId) }
    var editablePrinter by rememberSaveable(printer) { mutableStateOf(printer) }
    var editablePrinterId by rememberSaveable(printerId) { mutableStateOf(printerId) }
    var branches by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var signers by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var printers by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var listError by remember { mutableStateOf<String?>(null) }
    var listsLoading by remember { mutableStateOf(false) }

    LaunchedEffect(serverUrl) {
        listsLoading = true
        listError = null
        runCatching {
            val api = ApiClient.settingsApi(serverUrl)
            val branchItems = api.branches().map { SelectOption(it.id, it.name) }
            val signerItems = api.signers().map { SelectOption(it.id, "${it.last_name} ${it.first_name}") }
            val printerItems = api.printers().items.filter { it.kind == "zpl" }.map { SelectOption(it.id, it.displayName()) }
            Triple(branchItems, signerItems, printerItems)
        }.onSuccess { (branchItems, signerItems, printerItems) ->
            branches = branchItems
            signers = signerItems
            printers = printerItems
        }.onFailure {
            listError = "Не удалось загрузить списки"
        }
        listsLoading = false
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            ServiceTopBar(onBack = onBack)
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SectionLabel("Учётная запись")
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                            .background(Color.White),
                    ) {
                        ServiceInfoRow("Оператор", operator)
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SectionLabel("Параметры отправки")
                    ServiceCard {
                        SettingsField(
                            label = "Адрес сервера",
                            value = editableServerUrl,
                            onValueChange = { editableServerUrl = it },
                            placeholder = "http://127.0.0.1:8080",
                        )
                        SettingsDropdown(
                            label = "Филиал отправки",
                            value = editableBranch,
                            onValueChange = {
                                editableBranchId = it.id
                                editableBranch = it.label
                            },
                            options = branches,
                            placeholder = "Не выбран",
                        )
                        SettingsDropdown(
                            label = "Подписант",
                            value = editableSigner,
                            onValueChange = {
                                editableSignerId = it.id
                                editableSigner = it.label
                            },
                            options = signers,
                            placeholder = "Не выбран",
                        )
                        SettingsDropdown(
                            label = "ZPL-принтер",
                            value = editablePrinter,
                            onValueChange = {
                                editablePrinterId = it.id
                                editablePrinter = it.label
                            },
                            options = printers,
                            placeholder = "Не выбран",
                        )
                        if (listsLoading) {
                            Text("Загрузка...", style = MaterialTheme.typography.labelSmall, color = FgLabel)
                        }
                        if (listError != null) {
                            Text(listError.orEmpty(), style = MaterialTheme.typography.labelSmall, color = BrandRed)
                        }
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SectionLabel("Об устройстве")
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                            .background(Color.White),
                    ) {
                        ServiceInfoRow("ТСД", android.os.Build.MODEL ?: "Android")
                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(BorderLine))
                        ServiceInfoRow("Версия", "v1.2.0 · build 1")
                    }
                }
            }
            BottomBar {
                Button(
                    onClick = onLogout,
                    modifier = Modifier.height(56.dp).weight(0.4f),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = DangerBg),
                    elevation = ButtonDefaults.buttonElevation(0.dp),
                    border = BorderStroke(1.dp, Color(0xFFF3C2C2)),
                ) {
                    Text("Выйти", style = MaterialTheme.typography.bodyMedium, color = BrandRed)
                }
                Button(
                    onClick = {
                        onSaveSettings(
                            editableServerUrl.trim(),
                            editableBranchId,
                            editableBranch.trim(),
                            editableSignerId,
                            editableSigner.trim(),
                            editablePrinterId,
                            editablePrinter.trim(),
                        )
                    },
                    modifier = Modifier.weight(0.6f).height(56.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Сохранить", style = MaterialTheme.typography.titleMedium)
                }
            }
            ConnBanner(isOnline = isOnline)
        }
    }
}

@Composable
private fun SettingsField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        singleLine = true,
        label = { Text(label) },
        placeholder = { Text(placeholder) },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsDropdown(
    label: String,
    value: String,
    onValueChange: (SelectOption) -> Unit,
    options: List<SelectOption>,
    placeholder: String,
) {
    var expanded by remember { mutableStateOf(false) }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
        modifier = Modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth(),
            singleLine = true,
            label = { Text(label) },
            placeholder = { Text(placeholder) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            if (options.isEmpty()) {
                DropdownMenuItem(
                    text = { Text("Нет данных") },
                    onClick = { expanded = false },
                )
            } else {
                options.forEach { option ->
                    DropdownMenuItem(
                        text = { Text(option.label) },
                        onClick = {
                            onValueChange(option)
                            expanded = false
                        },
                    )
                }
            }
        }
    }
}

data class SelectOption(
    val id: String,
    val label: String,
)

private fun PrinterDto.displayName(): String {
    val address = if (!host.isNullOrBlank() && port != null) " · $host:$port" else ""
    return "$name$address"
}

@Composable
private fun ServiceTopBar(onBack: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .background(GradBlue)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(44.dp)) {
            Icon(
                painter = painterResource(R.drawable.ic_arrow_left),
                contentDescription = "Назад",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Text(
            text = "Сервисное меню",
            color = MaterialTheme.colorScheme.onPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
    }
}

@Composable
private fun ServiceCard(content: @Composable () -> Unit) {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            content()
        }
    }
}

@Composable
private fun ServiceRow(title: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.bodyMedium, color = BrandInk.copy(alpha = 0.72f))
        Text(value, style = MaterialTheme.typography.labelMedium, color = BrandInk)
    }
}

@Composable
private fun ServiceInfoRow(title: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.bodyMedium, color = BrandInk)
        Text(value, style = MaterialTheme.typography.labelSmall, color = FgMuted)
    }
}

@Composable
private fun ConnBanner(isOnline: Boolean, label: String? = null) {
    val dotColor = if (isOnline) SuccessGreen else BrandRed
    val text = label ?: if (isOnline) "Сеть · 1С · Принтер готовы" else "Нет связи с сервером"
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .drawBehind {
                drawLine(BorderLine, start = Offset(0f, 0f), end = Offset(size.width, 0f), strokeWidth = 1.dp.toPx())
            }
            .padding(horizontal = 14.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(dotColor),
        )
        Text(text, style = MaterialTheme.typography.labelSmall, color = FgLabel)
        Spacer(modifier = Modifier.weight(1f))
        Text("v1.2.0", style = MaterialTheme.typography.labelSmall, color = FgLabel.copy(alpha = 0.55f))
    }
}

@Composable
private fun ActionGrid(
    isCreatingEnvelope: Boolean,
    onCreateEnvelope: () -> Unit,
    onOpenVerify: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        ActionTile(
            title = if (isCreatingEnvelope) "Создание" else "Новый конверт",
            subtitle = if (isCreatingEnvelope) "Подождите" else "Регистрация",
            icon = R.drawable.ic_package_plus,
            modifier = Modifier.weight(1f),
            isLoading = isCreatingEnvelope,
            onClick = onCreateEnvelope,
        )
        ActionTile(
            title = "Проверить",
            subtitle = "Верификация",
            icon = R.drawable.ic_scan_line,
            modifier = Modifier.weight(1f),
            altTint = true,
            onClick = onOpenVerify,
        )
    }
}

@Composable
private fun VerifyStartScreen(
    isOnline: Boolean,
    message: String?,
    error: String?,
    onBack: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            RegisterTopBar(onBack = onBack, title = "Верификация", subtitle = "Сканируйте штрихкод конверта")
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                ScanTarget(
                    label = "Наведите сканер на штрихкод конверта",
                    hint = "После сканирования откроется список документов",
                    armed = error == null,
                )
                if (message != null) ScanFeedbackBanner(message, isError = false)
                if (error != null) ScanFeedbackBanner(error, isError = true)
            }
            BottomBar {
                Button(
                    onClick = onBack,
                    modifier = Modifier.size(56.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                    border = BorderStroke(1.dp, BorderSoft),
                    elevation = ButtonDefaults.buttonElevation(0.dp),
                    contentPadding = PaddingValues(0.dp),
                ) {
                    Icon(painter = painterResource(R.drawable.ic_arrow_left), contentDescription = "Назад", tint = FgMuted)
                }
            }
            ConnBanner(isOnline = isOnline)
        }
    }
}

@Composable
private fun VerifyScreen(
    envelope: EnvelopeDto,
    isOnline: Boolean,
    message: String?,
    error: String?,
    onBack: () -> Unit,
    onFinish: () -> Unit,
) {
    val scannedCount = envelope.documents.count { it.scanned_at_verification != null }
    val totalCount = envelope.documents.size
    val missingCount = totalCount - scannedCount
    val allScanned = totalCount > 0 && scannedCount == totalCount

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            RegisterTopBar(
                onBack = onBack,
                title = "Верификация",
                subtitle = "$scannedCount/$totalCount отсканировано",
            )
            VerifyEnvelopeHero(
                envelopeNumber = envelope.number,
                status = envelope.status,
                scannedCount = scannedCount,
                totalCount = totalCount,
                allScanned = allScanned,
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
            ) {
                if (!allScanned) {
                    ScanTarget(
                        label = "Сканируйте следующий документ",
                        hint = "Осталось ${missingCount}",
                        armed = true,
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                if (message != null) {
                    Box(modifier = Modifier.padding(horizontal = 14.dp)) {
                        ScanFeedbackBanner(message, isError = false)
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }
                if (error != null) {
                    Box(modifier = Modifier.padding(horizontal = 14.dp)) {
                        ScanFeedbackBanner(error, isError = true)
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }
                Box(modifier = Modifier.padding(horizontal = 14.dp)) {
                    SectionLabel("Состав конверта")
                }
                Spacer(modifier = Modifier.height(8.dp))
                if (envelope.documents.isEmpty()) {
                    Box(modifier = Modifier.padding(14.dp)) {
                        Text("В конверте нет документов", style = MaterialTheme.typography.bodyMedium, color = FgMuted)
                    }
                } else {
                    Column(
                        modifier = Modifier
                            .padding(horizontal = 14.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                            .background(Color.White),
                    ) {
                        envelope.documents.forEachIndexed { i, doc ->
                            if (i > 0) Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(BorderLine))
                            DocRow(
                                index = i + 1,
                                kind = doc.doc_kind,
                                number = doc.doc_number,
                                date = doc.doc_date.toDisplayDate(),
                                scanned = doc.scanned_at_verification != null,
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(14.dp))
            }
            BottomBar {
                if (allScanned) {
                    Button(
                        onClick = onFinish,
                        modifier = Modifier.weight(1f).height(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = SuccessGreen),
                    ) {
                        Text("Завершить сверку", style = MaterialTheme.typography.titleMedium)
                    }
                } else {
                    Button(
                        onClick = onBack,
                        modifier = Modifier.size(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                        border = BorderStroke(1.dp, BorderSoft),
                        elevation = ButtonDefaults.buttonElevation(0.dp),
                        contentPadding = PaddingValues(0.dp),
                    ) {
                        Icon(painter = painterResource(R.drawable.ic_arrow_left), contentDescription = "Назад", tint = FgMuted)
                    }
                    Button(
                        onClick = onFinish,
                        modifier = Modifier.weight(1f).height(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = BrandRed),
                    ) {
                        Text("С расхождением", style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
    }
}

@Composable
private fun ActionTile(
    title: String,
    subtitle: String,
    icon: Int,
    modifier: Modifier = Modifier,
    isLoading: Boolean = false,
    altTint: Boolean = false,
    onClick: () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.height(110.dp),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, BorderSoft),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(if (altTint) SuccessBg else SurfaceTint),
                contentAlignment = Alignment.Center,
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = if (altTint) SuccessGreen else BrandBlue,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Icon(
                        painter = painterResource(icon),
                        contentDescription = null,
                        tint = if (altTint) SuccessGreen else BrandBlue,
                        modifier = Modifier.size(22.dp),
                    )
                }
            }
            Column {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    color = BrandInk,
                )
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = FgMuted,
                )
            }
        }
    }
}

private val GradBlue = Brush.horizontalGradient(
    0f to Color(0xFF1B2848),
    0.55f to Color(0xFF243560),
    1f to Color(0xFF2874B9),
)

private val statusLabels = mapOf(
    "draft" to "Черновик",
    "sealed" to "Запечатан",
    "verified" to "Сверен",
    "verified_with_discrepancy" to "С расхождением",
)

@Composable
private fun StatusPill(status: String, onDark: Boolean = false) {
    val (bg, fg, dotColor) = when (status) {
        "draft" -> Triple(Color(0xFFF3F4F6), FgMuted, FgLabel)
        "sealed" -> Triple(WarningBg, WarningOrange, WarningOrange)
        "verified" -> Triple(SuccessBg, SuccessGreen, SuccessGreen)
        "verified_with_discrepancy" -> Triple(DangerBg, BrandRed, BrandRed)
        else -> Triple(Color(0xFFF3F4F6), FgMuted, FgLabel)
    }
    val pillBg = if (onDark) Color.White.copy(alpha = 0.18f) else bg
    val pillFg = if (onDark) Color.White else fg
    val pillDot = if (onDark) Color.White else dotColor
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(pillBg)
            .padding(horizontal = 8.dp, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Box(modifier = Modifier.size(5.dp).clip(CircleShape).background(pillDot))
        Text(
            statusLabels[status] ?: status,
            style = MaterialTheme.typography.labelMedium,
            color = pillFg,
        )
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = FgLabel,
        letterSpacing = 0.6.sp,
        modifier = Modifier.padding(bottom = 0.dp),
    )
}

@Composable
private fun ScanTarget(label: String, hint: String, armed: Boolean = true) {
    val infiniteTransition = rememberInfiniteTransition(label = "scan-pulse")
    val glow by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = if (armed) 1f else 0f,
        animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse),
        label = "scan-glow",
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .drawBehind {
                val dashEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 8f), 0f)
                drawRoundRect(
                    color = Color(0xFF1D71B8).copy(alpha = if (armed) 0.5f + glow * 0.5f else 0.4f),
                    style = Stroke(width = 1.5.dp.toPx(), pathEffect = dashEffect),
                    cornerRadius = CornerRadius(10.dp.toPx()),
                )
            }
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(SurfaceTint),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_scan_line),
                contentDescription = null,
                tint = BrandBlue,
                modifier = Modifier.size(22.dp),
            )
        }
        Column {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = BrandInk, fontWeight = FontWeight.Medium)
            Text(hint, style = MaterialTheme.typography.labelSmall, color = FgMuted)
        }
    }
}

@Composable
private fun DocRow(
    index: Int,
    kind: String,
    number: String,
    date: String,
    scanned: Boolean? = null,
    showRemove: Boolean = false,
    onRemove: (() -> Unit)? = null,
) {
    val bg = when (scanned) {
        true -> SuccessBg
        false -> Color(0xFFFCE8E8)
        null -> Color.White
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(bg)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            "$index",
            style = MaterialTheme.typography.labelSmall,
            color = FgLabel,
            modifier = Modifier.width(18.dp),
        )
        Box(
            modifier = Modifier
                .size(22.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(SurfaceTint),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_package_plus),
                contentDescription = null,
                tint = BrandBlue,
                modifier = Modifier.size(13.dp),
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(3.dp))
                        .background(SurfaceTint)
                        .padding(horizontal = 5.dp, vertical = 1.dp),
                ) {
                    Text(kind, style = MaterialTheme.typography.labelMedium, color = BrandBlue)
                }
                Text(
                    "№$number",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (scanned == false) FgMuted else BrandInk,
                )
            }
            Text(date, style = MaterialTheme.typography.labelSmall, color = FgMuted)
        }
        when {
            scanned == true -> Icon(
                painter = painterResource(R.drawable.ic_scan_line),
                contentDescription = "Считан",
                tint = SuccessGreen,
                modifier = Modifier.size(18.dp),
            )
            scanned == false -> Icon(
                painter = painterResource(R.drawable.ic_scan_line),
                contentDescription = "Не считан",
                tint = BorderSoft,
                modifier = Modifier.size(18.dp),
            )
            showRemove && onRemove != null -> IconButton(
                onClick = onRemove,
                modifier = Modifier.size(28.dp),
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_arrow_left),
                    contentDescription = "Удалить",
                    tint = BrandRed,
                    modifier = Modifier.size(16.dp),
                )
            }
        }
    }
}

@Composable
private fun ScanFeedbackBanner(message: String?, isError: Boolean) {
    if (message == null) return
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(if (isError) DangerBg else SuccessBg)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (isError) BrandRed else SuccessGreen),
        )
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = if (isError) BrandRed else SuccessGreen,
        )
    }
}

@Composable
private fun BottomBar(content: @Composable () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .drawBehind {
                drawLine(Color(0xFFDDE4EF), start = Offset(0f, 0f), end = Offset(size.width, 0f), strokeWidth = 1.dp.toPx())
            }
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        content()
    }
}

@Composable
private fun RecentEnvelopeStub() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
            .background(Color.White)
            .padding(40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(SurfaceAlt),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_package_plus),
                contentDescription = null,
                tint = FgLabel,
                modifier = Modifier.size(26.dp),
            )
        }
        Text("Конвертов пока нет", style = MaterialTheme.typography.titleMedium, color = BrandInk)
        Text("Конверты появятся после подключения", style = MaterialTheme.typography.labelSmall, color = FgMuted)
    }
}

@Preview(widthDp = 360, heightDp = 720)
@Composable
private fun TsdShellPreview() {
    KonvertTrackTheme {
        TsdShell(
            operator = "Иванов",
            serverUrl = "http://127.0.0.1:8080",
            isOnline = true,
            onOpenService = {},
            onOpenVerify = {},
            onEnvelopeCreated = {},
        )
    }
}
