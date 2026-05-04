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
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
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
import ru.technoavia.konverttrack.ui.theme.BrandBlueLight
import ru.technoavia.konverttrack.ui.theme.BrandBlueMid
import ru.technoavia.konverttrack.ui.theme.BrandRed
import ru.technoavia.konverttrack.ui.theme.BrandGreen
import ru.technoavia.konverttrack.ui.theme.BrandInk
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.statusBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
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
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(modifier = Modifier.height(32.dp))
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Image(
                    painter = painterResource(R.drawable.logo_lockup),
                    contentDescription = "ТехноКонверт",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(84.dp)
                        .clickable {
                            logoTapCount += 1
                            if (logoTapCount >= 5) {
                                logoTapCount = 0
                                showServerDialog = true
                            }
                        },
                    contentScale = ContentScale.Fit,
                )
                Text("Учёт передачи документов · ТСД", style = MaterialTheme.typography.labelSmall)
                Text(
                    "Сканируйте QR входа или введите оператора и PIN",
                    style = MaterialTheme.typography.labelSmall,
                    color = BrandInk.copy(alpha = 0.62f),
                )
                OutlinedTextField(
                    value = username,
                    onValueChange = {
                        username = it
                        errorText = null
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("Оператор") },
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = {
                        password = it.filter(Char::isDigit).take(4)
                        errorText = null
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("PIN-код") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    visualTransformation = PasswordVisualTransformation(),
                )
                if (errorText != null) {
                    Text(
                        text = errorText.orEmpty(),
                        color = BrandRed,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Button(
                    onClick = {
                        submitLogin()
                    },
                    enabled = !isLoading && serverUrl.isNotBlank() && username.isNotBlank() && password.length == 4,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(6.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Text("Войти", style = MaterialTheme.typography.titleMedium)
                    }
                }
                Text(
                    text = serverUrl.ifBlank { "Адрес сервера не задан" },
                    style = MaterialTheme.typography.labelSmall,
                    color = BrandInk.copy(alpha = 0.45f),
                )
                Text("v1.2.0 · build 1", style = MaterialTheme.typography.labelSmall, color = BrandInk.copy(alpha = 0.45f))
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
            TopBar(onOpenService = onOpenService)
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
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
                    Text(createError.orEmpty(), color = BrandRed, style = MaterialTheme.typography.bodyMedium)
                }
                RecentEnvelopeStub()
            }
            ConnectionFooter(isOnline = isOnline)
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

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            RegisterTopBar(onBack = onBack, title = if (envelope.status == "sealed") "Конверт запечатан" else "Новый конверт")
            if (envelope.status == "sealed") {
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
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    EnvelopeHero(envelope)
                    if (message != null) {
                        Text(message, color = BrandGreen, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (error != null) {
                        Text(error, color = BrandRed, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (sealMessage != null) {
                        Text(sealMessage.orEmpty(), color = BrandGreen, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (sealError != null) {
                        Text(sealError.orEmpty(), color = BrandRed, style = MaterialTheme.typography.bodyMedium)
                    }
                    Text("Документы", style = MaterialTheme.typography.titleMedium)
                    if (envelope.documents.isEmpty()) {
                        EmptyRegisterState()
                    } else {
                        envelope.documents.forEach { doc ->
                            ServiceCard {
                                ServiceRow(doc.doc_kind, doc.doc_number)
                                ServiceRow("Дата", doc.doc_date.toDisplayDate())
                            }
                        }
                    }
                }
                Button(
                    onClick = sealAction,
                    enabled = !isSealing,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp)
                        .padding(horizontal = 16.dp),
                    shape = RoundedCornerShape(6.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandGreen),
                ) {
                    if (isSealing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Text("Запечатать", style = MaterialTheme.typography.titleMedium)
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }
            ConnectionFooter(isOnline = isOnline)
        }
    }
}

@Composable
private fun RegisterTopBar(onBack: () -> Unit, title: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .background(BrandInk)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(
                painter = painterResource(R.drawable.ic_arrow_left),
                contentDescription = "Назад",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Text(
            text = title,
            color = MaterialTheme.colorScheme.onPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
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
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        EnvelopeHero(envelope)
        ServiceCard {
            Text("Конверт запечатан", style = MaterialTheme.typography.titleMedium, color = BrandGreen)
            Text("Документов: ${envelope.documents.size}", style = MaterialTheme.typography.bodyMedium)
            Text("Можно распечатать этикетку и вернуться на главный экран", style = MaterialTheme.typography.bodyMedium)
        }
        if (printMessage != null) {
            Text(printMessage, color = BrandGreen, style = MaterialTheme.typography.bodyMedium)
        }
        if (printError != null) {
            Text(printError, color = BrandRed, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(modifier = Modifier.weight(1f))
        Button(
            onClick = onPrint,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(6.dp),
            colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
        ) {
            Text("Распечатать этикетку", style = MaterialTheme.typography.titleMedium)
        }
        Button(
            onClick = onDone,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(6.dp),
            colors = ButtonDefaults.buttonColors(containerColor = BrandInk),
        ) {
            Text("На главный экран", style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
private fun EnvelopeHero(envelope: EnvelopeDto) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Brush.linearGradient(listOf(BrandBlueMid, BrandBlue, BrandBlueLight)))
                .padding(16.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(envelope.number, color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.titleLarge)
                Text("Черновик", color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.82f), style = MaterialTheme.typography.labelMedium)
                Text("Документов: ${envelope.documents.size}", color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.82f))
                Text(envelope.barcode, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.72f), style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun VerifyEnvelopeHero(
    envelopeNumber: String,
    scannedCount: Int,
    totalCount: Int,
    allScanned: Boolean,
) {
    val pulse = if (allScanned) {
        rememberInfiniteTransition(label = "verify-complete").animateFloat(
            initialValue = 0.72f,
            targetValue = 1.0f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 700),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "verify-complete-alpha",
        ).value
    } else {
        1.0f
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Brush.linearGradient(listOf(BrandBlueMid, BrandBlue, BrandBlueLight)))
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(envelopeNumber, color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.titleLarge)
                Text("Сверка документов", color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.82f), style = MaterialTheme.typography.labelMedium)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = if (allScanned) "✓ $scannedCount/$totalCount" else "$scannedCount/$totalCount",
                    color = if (allScanned) BrandGreen else MaterialTheme.colorScheme.onPrimary,
                    style = MaterialTheme.typography.titleLarge,
                )
                if (allScanned) {
                    Text(
                        "Все документы считаны",
                        color = MaterialTheme.colorScheme.onPrimary.copy(alpha = pulse),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
        }
    }
}

@Composable
private fun EmptyRegisterState() {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Документов пока нет", style = MaterialTheme.typography.titleMedium)
            Text("Сканируйте документы физической кнопкой ТСД", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun TopBar(onOpenService: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .background(BrandInk)
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Image(
            painter = painterResource(R.drawable.logo_icon),
            contentDescription = null,
            modifier = Modifier.size(30.dp),
        )
        Column(modifier = Modifier.weight(1f)) {
            Text("ТехноКонверт", color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Bold)
            Text("ТСД · рабочее место", color = BrandBlueLight, style = MaterialTheme.typography.labelSmall)
        }
        IconButton(onClick = onOpenService) {
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
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("Сервисное меню", style = MaterialTheme.typography.titleLarge)
                ServiceCard {
                    ServiceRow("Оператор", operator)
                    ServiceRow("Подключение", if (isOnline) "Сервер онлайн" else "Нет подключения")
                }
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
                        Text("Загрузка списков", style = MaterialTheme.typography.labelSmall, color = BrandInk.copy(alpha = 0.55f))
                    }
                    if (listError != null) {
                        Text(listError.orEmpty(), style = MaterialTheme.typography.bodyMedium, color = BrandRed)
                    }
                }
                ServiceCard {
                    ServiceRow("ТСД", android.os.Build.MODEL ?: "Android")
                    ServiceRow("Производитель", android.os.Build.MANUFACTURER ?: "Неизвестно")
                    ServiceRow("Версия", "v1.2.0 · build 1")
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
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(6.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Сохранить", style = MaterialTheme.typography.titleMedium)
                }
                Button(
                    onClick = onLogout,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(6.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandRed),
                ) {
                    Text("Выйти", style = MaterialTheme.typography.titleMedium)
                }
            }
            ConnectionFooter(isOnline = isOnline)
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
            .background(BrandInk)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(
                painter = painterResource(R.drawable.ic_arrow_left),
                contentDescription = "Назад",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Text(
            text = "Настройки",
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
private fun ConnectionFooter(isOnline: Boolean) {
    val dotColor = if (isOnline) BrandGreen else MaterialTheme.colorScheme.error
    val text = if (isOnline) "Сервер онлайн" else "Нет подключения"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(dotColor),
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(text, style = MaterialTheme.typography.labelSmall, color = BrandInk.copy(alpha = 0.55f))
        }
        Text("v1.2.0 · build 1", style = MaterialTheme.typography.labelSmall, color = BrandInk.copy(alpha = 0.45f))
    }
}

@Composable
private fun ActionGrid(
    isCreatingEnvelope: Boolean,
    onCreateEnvelope: () -> Unit,
    onOpenVerify: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        ActionTile(
            title = if (isCreatingEnvelope) "Создание" else "Новый конверт",
            subtitle = if (isCreatingEnvelope) "Подождите" else "Регистрация",
            icon = R.drawable.ic_package_plus,
            modifier = Modifier.weight(1f),
            onClick = onCreateEnvelope,
        )
        ActionTile(
            title = "Проверить",
            subtitle = "Сверка",
            icon = R.drawable.ic_scan_line,
            modifier = Modifier.weight(1f),
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
            RegisterTopBar(onBack = onBack, title = "Сверка конверта")
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                ServiceCard {
                    Text("Сканируйте штрихкод конверта", style = MaterialTheme.typography.titleMedium)
                    Text("После сканирования откроется список документов для сверки", style = MaterialTheme.typography.bodyMedium)
                }
                if (message != null) {
                    Text(message, color = BrandGreen, style = MaterialTheme.typography.bodyMedium)
                }
                if (error != null) {
                    Text(error, color = BrandRed, style = MaterialTheme.typography.bodyMedium)
                }
            }
            ConnectionFooter(isOnline = isOnline)
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
            RegisterTopBar(onBack = onBack, title = "Сверка")
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                VerifyEnvelopeHero(
                    envelopeNumber = envelope.number,
                    scannedCount = scannedCount,
                    totalCount = totalCount,
                    allScanned = allScanned,
                )
                if (message != null) {
                    Text(message, color = BrandGreen, style = MaterialTheme.typography.bodyMedium)
                }
                if (error != null) {
                    Text(error, color = BrandRed, style = MaterialTheme.typography.bodyMedium)
                }
                Text("Документы конверта", style = MaterialTheme.typography.titleMedium)
                if (envelope.documents.isEmpty()) {
                    ServiceCard {
                        Text("В конверте нет документов", style = MaterialTheme.typography.bodyMedium)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(envelope.documents, key = { it.id }) { doc ->
                            Card(
                                shape = RoundedCornerShape(8.dp),
                                colors = CardDefaults.cardColors(
                                    containerColor = if (doc.scanned_at_verification != null) {
                                        BrandGreen.copy(alpha = 0.10f)
                                    } else {
                                        BrandRed.copy(alpha = 0.08f)
                                    },
                                ),
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Column(
                                    modifier = Modifier.padding(14.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    ServiceRow(doc.doc_kind, doc.doc_number)
                                    ServiceRow("Дата", doc.doc_date.toDisplayDate())
                                    ServiceRow(
                                        "Статус",
                                        if (doc.scanned_at_verification != null) "Считан" else "Не считан",
                                    )
                                    if (doc.scanned_at_verification != null) {
                                        ServiceRow("Считан в", doc.scanned_at_verification.replace("T", " ").take(16))
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Button(
                onClick = onFinish,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(6.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (missingCount == 0) BrandGreen else BrandRed,
                ),
            ) {
                Text(
                    if (missingCount == 0) "Завершить сверку" else "Завершить с расхождением",
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            ConnectionFooter(isOnline = isOnline)
        }
    }
}

@Composable
private fun ActionTile(
    title: String,
    subtitle: String,
    icon: Int,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.height(124.dp),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Brush.linearGradient(listOf(BrandBlueMid, BrandBlue, BrandBlueLight)))
                .padding(12.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.14f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painter = painterResource(icon),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onPrimary,
                    modifier = Modifier.size(20.dp),
                )
            }
            Column {
                Spacer(modifier = Modifier.weight(1f))
                Text(title, color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Bold)
                Text(subtitle, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f))
            }
        }
    }
}

@Composable
private fun RecentEnvelopeStub() {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Последние", style = MaterialTheme.typography.titleMedium)
            Text("Конверты появятся после подключения API", style = MaterialTheme.typography.bodyMedium)
        }
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
