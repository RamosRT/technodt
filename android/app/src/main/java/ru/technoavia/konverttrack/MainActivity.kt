package ru.technoavia.konverttrack

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.MediaPlayer
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.core.content.edit
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import kotlin.math.roundToInt
import org.json.JSONObject
import retrofit2.HttpException
import ru.technoavia.konverttrack.data.api.ApiClient
import ru.technoavia.konverttrack.data.api.DocumentAddRequest
import ru.technoavia.konverttrack.data.api.DocumentDto
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
                    onSaveLogin = { serverUrl, operator, assignedZplPrinterId, assignedA4PrinterId ->
                        prefs.edit {
                            putString("server_url", serverUrl)
                            putString("operator", operator)
                            if (!assignedZplPrinterId.isNullOrBlank()) {
                                putString("printer_id", assignedZplPrinterId)
                            }
                            if (!assignedA4PrinterId.isNullOrBlank()) {
                                putString("a4_printer_id", assignedA4PrinterId)
                            }
                        }
                    },
                    onClearLogin = {
                        prefs.edit { remove("operator") }
                    },
                    loadPreference = { key -> prefs.getString(key, "") ?: "" },
                    savePreference = { key, value -> prefs.edit { putString(key, value) } },
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
            "scandata",
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
            .mapNotNull { key -> bundle.getString(key) }
            .firstOrNull { it.isNotBlank() }
            ?.trim()
    }

    private companion object {
        const val TAG = "KonvertTrack"
        const val UROVO_SCAN_ACTION = "urovo.rcv.message"
        const val UROVO_DECODE_ACTION = "android.intent.ACTION_DECODE_DATA"
        const val MINDEO_SCAN_ACTION = "com.android.scanner.broadcast"
        val SCAN_ACTIONS = setOf(UROVO_SCAN_ACTION, UROVO_DECODE_ACTION, MINDEO_SCAN_ACTION)
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
private fun isCompactTsd(): Boolean {
    val configuration = LocalConfiguration.current
    return configuration.screenHeightDp <= 640 || configuration.screenWidthDp <= 360
}

@Composable
private fun AppRoot(
    savedServerUrl: String,
    onSaveLogin: (String, String, String?, String?) -> Unit,
    onClearLogin: () -> Unit,
    loadPreference: (String) -> String,
    savePreference: (String, String) -> Unit,
    bindServiceMenu: ((() -> Unit)?) -> Unit,
    bindBarcode: (((String) -> Unit)?) -> Unit,
    bindSealEnvelope: ((() -> Unit)?) -> Unit,
) {
    var showSplash by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        delay(1800L)
        showSplash = false
    }
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
    var a4Printer by rememberSaveable { mutableStateOf(loadPreference("a4_printer")) }
    var a4PrinterId by rememberSaveable { mutableStateOf(loadPreference("a4_printer_id")) }
    var currentEnvelope by remember { mutableStateOf<EnvelopeDto?>(null) }
    var verifyEnvelope by remember { mutableStateOf<EnvelopeDto?>(null) }
    var registerMessage by remember { mutableStateOf<String?>(null) }
    var registerError by remember { mutableStateOf<String?>(null) }
    var verifyMessage by remember { mutableStateOf<String?>(null) }
    var verifyError by remember { mutableStateOf<String?>(null) }
    var isRegisteringScan by remember { mutableStateOf(false) }
    var isVerifyingEnvelope by remember { mutableStateOf(false) }
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
                            isRegisteringScan = true
                            try {
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
                            } finally {
                                isRegisteringScan = false
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
                        isVerifyingEnvelope = true
                        try {
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
                        } finally {
                            isVerifyingEnvelope = false
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
                            isVerifyingEnvelope = true
                            try {
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
                            } finally {
                                isVerifyingEnvelope = false
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
                            isVerifyingEnvelope = true
                            try {
                                runCatching {
                                    ApiClient.envelopeApi(currentServerUrl).verifyFinish(envelopeId, VerifyFinishRequest(force = true))
                                }.onSuccess {
                                    verifyMessage = "Сверка завершена с расхождением"
                                    verifyEnvelope = null
                                    screen = "home"
                                }.onFailure { err ->
                                    verifyError = apiErrorText(err)
                                }
                            } finally {
                                isVerifyingEnvelope = false
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

    if (showSplash) {
        SplashScreen()
        return
    }

    if (operator == null) {
        LoginScreen(
            savedServerUrl = savedServerUrl,
            bindServiceMenu = bindServiceMenu,
            bindBarcode = bindBarcode,
            onLoginSuccess = { serverUrl, name, assignedPrinterId, assignedA4PrinterId ->
                onSaveLogin(serverUrl, name, assignedPrinterId, assignedA4PrinterId)
                currentServerUrl = serverUrl
                if (!assignedPrinterId.isNullOrBlank()) {
                    printerId = assignedPrinterId
                    savePreference("printer_id", assignedPrinterId)
                }
                if (!assignedA4PrinterId.isNullOrBlank()) {
                    a4PrinterId = assignedA4PrinterId
                    savePreference("a4_printer_id", assignedA4PrinterId)
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
            a4Printer = a4Printer,
            a4PrinterId = a4PrinterId,
            onBack = { screen = "home" },
            onSaveSettings = { server, selectedBranchId, newBranch, selectedSignerId, newSigner, selectedPrinterId, newPrinter, selectedA4PrinterId, newA4Printer ->
                currentServerUrl = server
                branchId = selectedBranchId
                branch = newBranch
                signerId = selectedSignerId
                signer = newSigner
                printerId = selectedPrinterId
                printer = newPrinter
                a4PrinterId = selectedA4PrinterId
                a4Printer = newA4Printer
                savePreference("server_url", server)
                savePreference("branch_id", selectedBranchId)
                savePreference("branch", newBranch)
                savePreference("signer_id", selectedSignerId)
                savePreference("signer", newSigner)
                savePreference("printer_id", selectedPrinterId)
                savePreference("printer", newPrinter)
                savePreference("a4_printer_id", selectedA4PrinterId)
                savePreference("a4_printer", newA4Printer)
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
            branchName = branch,
            signerName = signer,
            branchId = branchId,
            signerId = signerId,
            printerId = printerId,
            a4PrinterId = a4PrinterId,
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
            branchName = branch,
            signerName = signer,
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
                    isVerifyingEnvelope = true
                    try {
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
                    } finally {
                        isVerifyingEnvelope = false
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
            onOpenDraft = { envelope ->
                registerMessage = "Открыт черновик: ${envelope.number}"
                registerError = null
                currentEnvelope = envelope
                screen = "register"
            },
            onVerifyEnvelopeStarted = { envelope ->
                verifyEnvelope = envelope
                verifyMessage = "Конверт найден: ${envelope.number}"
                verifyError = null
                screen = "verify"
            },
            onEnvelopeCreated = { envelope ->
                registerMessage = null
                registerError = null
                currentEnvelope = envelope
                screen = "register"
            },
        )
    }

    if (isRegisteringScan) {
        BrandLoadingOverlay("Регистрируем документ...")
    }
    if (isVerifyingEnvelope) {
        BrandLoadingOverlay("Верифицируем конверт...")
    }
}

@Composable
private fun LoginScreen(
    savedServerUrl: String,
    bindServiceMenu: ((() -> Unit)?) -> Unit,
    bindBarcode: (((String) -> Unit)?) -> Unit,
    onLoginSuccess: (String, String, String?, String?) -> Unit,
) {
    val configuration = LocalConfiguration.current
    val compactHeight = configuration.screenHeightDp <= 700

    var serverUrl by rememberSaveable { mutableStateOf(savedServerUrl) }
    var username by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var logoTapCount by rememberSaveable { mutableIntStateOf(0) }
    var showServerDialog by rememberSaveable { mutableStateOf(savedServerUrl.isBlank()) }
    var passwordVisible by rememberSaveable { mutableStateOf(false) }
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
                    onLoginSuccess(
                        nextServerUrl.trim(),
                        response.operator,
                        response.assigned_zpl_printer_id,
                        response.assigned_a4_printer_id,
                    )
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

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    0f to Color.White,
                    0.55f to Color(0xFFF8FBFF),
                    1f to Color.White,
                ),
            ),
    ) {
        LoginDecorations()
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(modifier = Modifier.height(if (compactHeight) 34.dp else 62.dp))
            LoginLogoLockup(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(if (compactHeight) 76.dp else 86.dp)
                    .clickable {
                        logoTapCount += 1
                        if (logoTapCount >= 5) {
                            logoTapCount = 0
                            showServerDialog = true
                        }
                    },
            )
            Text(
                "Учёт передачи документов · ТСД",
                style = MaterialTheme.typography.bodyMedium,
                color = FgMuted,
            )
            Spacer(modifier = Modifier.height(if (compactHeight) 26.dp else 48.dp))
            LoginInputCard(
                icon = R.drawable.ic_user_round,
                label = "Имя оператора",
                value = username,
                onValueChange = {
                    username = it
                    errorText = null
                },
                placeholder = "ivan.petrov",
            )
            Spacer(modifier = Modifier.height(if (compactHeight) 14.dp else 22.dp))
            LoginInputCard(
                icon = R.drawable.ic_lock_keyhole,
                label = "Пароль",
                value = password,
                onValueChange = {
                    password = it.filter(Char::isDigit).take(4)
                    errorText = null
                },
                placeholder = "••••",
                keyboardType = KeyboardType.NumberPassword,
                visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = R.drawable.ic_eye,
                onTrailingClick = { passwordVisible = !passwordVisible },
            )
            if (errorText != null) {
                Spacer(modifier = Modifier.height(if (compactHeight) 12.dp else 18.dp))
                ScanFeedbackBanner(errorText, isError = true)
            } else {
                Spacer(modifier = Modifier.height(if (compactHeight) 18.dp else 30.dp))
            }
            Button(
                onClick = { submitLogin() },
                enabled = !isLoading && serverUrl.isNotBlank() && username.isNotBlank() && password.length == 4,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(62.dp)
                    .shadow(12.dp, RoundedCornerShape(10.dp), spotColor = BrandBlue.copy(alpha = 0.22f))
                    .clip(RoundedCornerShape(10.dp)),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.Transparent,
                    disabledContainerColor = Color(0xFFB8C7DC),
                ),
                contentPadding = PaddingValues(0.dp),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Brush.horizontalGradient(
                                0f to Color(0xFF0063C7),
                                1f to Color(0xFF4094F7),
                            ),
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("Войти", style = MaterialTheme.typography.titleLarge, color = Color.White)
                }
            }
            Spacer(modifier = Modifier.height(if (compactHeight) 10.dp else 16.dp))
            LoginDeviceIndicator(
                text = "Устройство: ${Build.MODEL.ifBlank { "ТСД" }}",
            )
            Spacer(modifier = Modifier.weight(1f))
            StaticLogoBadge(
                modifier = Modifier
                    .align(Alignment.End)
                    .offset(x = if (compactHeight) 10.dp else 18.dp, y = 0.dp),
            )
            Spacer(modifier = Modifier.height(if (compactHeight) 8.dp else 18.dp))
            Text("v1.4.0", style = MaterialTheme.typography.labelSmall, color = FgMuted)
            Spacer(modifier = Modifier.height(if (compactHeight) 14.dp else 34.dp))
        }
        if (isLoading) {
            BrandLoadingOverlay("Вход в систему...")
        }
    }
}

@Composable
private fun LoginLogoLockup(modifier: Modifier = Modifier) {
    val configuration = LocalConfiguration.current
    val compactWidth = configuration.screenWidthDp <= 360
    val logoFontSize = if (compactWidth) 26.sp else 32.sp
    val logoLineHeight = if (compactWidth) 30.sp else 36.sp

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        Box(modifier = Modifier.size(66.dp), contentAlignment = Alignment.Center) {
            Image(
                painter = painterResource(R.drawable.ic_launcher_foreground),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(0.82f),
                colorFilter = ColorFilter.tint(BrandInk),
            )
        }
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            "ТехноКонверт",
            style = TextStyle(
                color = BrandInk,
                fontSize = logoFontSize,
                lineHeight = logoLineHeight,
                fontWeight = FontWeight.Bold,
            ),
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Clip,
        )
    }
}

@Composable
private fun LoginDecorations() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .clickable(enabled = false, onClick = {}),
    ) {
        Box(
            modifier = Modifier
                .size(138.dp)
                .offset(x = (-118).dp, y = 70.dp)
                .rotate(45f)
                .clip(RoundedCornerShape(28.dp))
                .background(BrandInk),
        )
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .size(118.dp)
                .offset(x = 42.dp, y = 44.dp)
                .rotate(45f)
                .clip(RoundedCornerShape(26.dp))
                .background(Color(0xFFE4EEF9)),
        )
        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .size(width = 168.dp, height = 236.dp)
                .offset(x = (-70).dp, y = 54.dp)
                .rotate(45f)
                .clip(RoundedCornerShape(34.dp))
                .background(
                    Brush.linearGradient(
                        0f to BrandInk,
                        1f to Color(0xFF0C2347),
                    ),
                ),
        )
        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .size(width = 108.dp, height = 190.dp)
                .offset(x = 86.dp, y = 70.dp)
                .rotate(45f)
                .clip(RoundedCornerShape(28.dp))
                .background(
                    Brush.linearGradient(
                        0f to Color(0xFF4E9BF0).copy(alpha = 0.84f),
                        1f to Color(0xFFE4F0FF).copy(alpha = 0.78f),
                    ),
                ),
        )
    }
}

@Composable
private fun LoginInputCard(
    icon: Int,
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
    keyboardType: KeyboardType = KeyboardType.Text,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    trailingIcon: Int? = null,
    onTrailingClick: (() -> Unit)? = null,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(72.dp)
            .shadow(16.dp, RoundedCornerShape(10.dp), spotColor = BrandInk.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(10.dp))
            .background(Color.White.copy(alpha = 0.96f))
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            tint = BrandBlue,
            modifier = Modifier.size(32.dp),
        )
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = FgMuted)
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                textStyle = TextStyle(
                    color = BrandInk,
                    fontSize = 19.sp,
                    lineHeight = 24.sp,
                    fontWeight = FontWeight.Medium,
                ),
                keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
                visualTransformation = visualTransformation,
                decorationBox = { innerTextField ->
                    if (value.isBlank()) {
                        Text(
                            placeholder,
                            style = MaterialTheme.typography.bodyMedium,
                            color = FgLabel,
                        )
                    }
                    innerTextField()
                },
            )
        }
        if (trailingIcon != null && onTrailingClick != null) {
            IconButton(onClick = onTrailingClick, modifier = Modifier.size(44.dp)) {
                Icon(
                    painter = painterResource(trailingIcon),
                    contentDescription = "Показать пароль",
                    tint = Color(0xFF425577),
                    modifier = Modifier.size(28.dp),
                )
            }
        }
    }
}

@Composable
private fun LoginDeviceIndicator(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_smartphone),
            contentDescription = null,
            tint = FgLabel.copy(alpha = 0.72f),
            modifier = Modifier.size(13.dp),
        )
        Spacer(modifier = Modifier.width(5.dp))
        Text(
            text,
            style = MaterialTheme.typography.labelSmall,
            color = FgLabel.copy(alpha = 0.74f),
        )
    }
}

@Composable
private fun StaticLogoBadge(modifier: Modifier = Modifier) {
    Box(modifier = modifier.size(114.dp), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            val radius = size.minDimension * 0.38f
            val strokeW = size.minDimension * 0.07f
            val colors = listOf(
                BrandBlue,
                Color(0xFFDCE9F7),
                Color(0xFFE9F1FA),
                BrandRed,
                Color(0xFFDCE9F7),
                BrandBlueLight,
                Color(0xFFDCE9F7),
                Color(0xFFE9F1FA),
            )
            for (i in 0..7) {
                drawArc(
                    color = colors[i],
                    startAngle = -90f + i * 45f + 7f,
                    sweepAngle = 28f,
                    useCenter = false,
                    topLeft = Offset(cx - radius, cy - radius),
                    size = Size(radius * 2f, radius * 2f),
                    style = Stroke(width = strokeW, cap = StrokeCap.Round),
                )
            }
        }
        Image(
            painter = painterResource(R.drawable.ic_launcher_foreground),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(0.46f),
            colorFilter = ColorFilter.tint(Color(0xFF155CA8)),
        )
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
            @Suppress("DEPRECATION")
            URLDecoder.decode(query, "UTF-8").parseCandidateTokens()
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
    onOpenDraft: (EnvelopeDto) -> Unit,
    onVerifyEnvelopeStarted: (EnvelopeDto) -> Unit,
    onEnvelopeCreated: (EnvelopeDto) -> Unit,
) {
    var isCreatingEnvelope by remember { mutableStateOf(false) }
    var isLoadingRecent by remember { mutableStateOf(false) }
    var isOpeningRecent by remember { mutableStateOf(false) }
    var recent by remember { mutableStateOf<List<EnvelopeDto>>(emptyList()) }
    var createError by remember { mutableStateOf<String?>(null) }
    var recentError by remember { mutableStateOf<String?>(null) }
    var verifiedWarning by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    fun refreshRecent() {
        scope.launch {
            isLoadingRecent = true
            recentError = null
            runCatching {
                ApiClient.envelopeApi(serverUrl).recentEnvelopes()
            }.onSuccess { items ->
                recent = items
            }.onFailure { error ->
                recentError = loginErrorText(error)
            }
            isLoadingRecent = false
        }
    }

    fun openRecentEnvelope(envelope: EnvelopeDto) {
        when (envelope.status) {
            "draft" -> {
                playScanSound(context, success = true)
                onOpenDraft(envelope)
            }
            "sealed" -> {
                scope.launch {
                    isOpeningRecent = true
                    recentError = null
                    runCatching {
                        ApiClient.envelopeApi(serverUrl).verifyStart(envelope.id)
                    }.onSuccess { started ->
                        playScanSound(context, success = true)
                        onVerifyEnvelopeStarted(started)
                    }.onFailure { error ->
                        playScanSound(context, success = false)
                        recentError = apiErrorText(error)
                    }
                    isOpeningRecent = false
                }
            }
            "verified", "verified_with_discrepancy" -> {
                playScanSound(context, success = false)
                verifiedWarning = "Конверт ${envelope.number} уже верифицирован. Повторное открытие недоступно."
            }
            else -> {
                playScanSound(context, success = false)
                verifiedWarning = "Конверт ${envelope.number} в статусе ${envelope.status}"
            }
        }
    }

    LaunchedEffect(serverUrl, operator) {
        if (serverUrl.isNotBlank() && operator.isNotBlank()) {
            refreshRecent()
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
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
                RecentEnvelopesBlock(
                    envelopes = recent,
                    isLoading = isLoadingRecent,
                    error = recentError,
                    onEnvelopeClick = ::openRecentEnvelope,
                )
            }
            ConnBanner(isOnline = isOnline)
        }
        if (isOpeningRecent) {
            BrandLoadingOverlay("Открываем конверт...")
        }
        }
    }

    if (verifiedWarning != null) {
        AlertDialog(
            onDismissRequest = { verifiedWarning = null },
            title = { Text("Конверт закрыт") },
            text = { Text(verifiedWarning.orEmpty()) },
            confirmButton = {
                Button(
                    onClick = { verifiedWarning = null },
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Понятно")
                }
            },
        )
    }
}

@Composable
private fun RegisterScreen(
    envelope: EnvelopeDto,
    serverUrl: String,
    isOnline: Boolean,
    message: String?,
    error: String?,
    branchName: String,
    signerName: String,
    branchId: String,
    signerId: String,
    printerId: String,
    a4PrinterId: String,
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
    var showSealSignerSheet by remember { mutableStateOf(false) }
    var sealSignersList by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var sealSignersError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    LaunchedEffect(serverUrl) {
        runCatching {
            ApiClient.settingsApi(serverUrl).signers()
                .map { SelectOption(it.id, "${it.last_name} ${it.first_name}") }
        }.onSuccess { sealSignersList = it }
         .onFailure { sealSignersError = "Не удалось загрузить список подписантов" }
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
    Box(modifier = Modifier.fillMaxSize()) {
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
            EnvelopeHero(
                envelope = envelope,
                branchName = branchName,
                signerName = signerName,
            )
            if (sealed) {
                SealedEnvelopeScreen(
                    envelope = envelope,
                    printMessage = printMessage,
                    printError = printError,
                    onPrintLabel = {
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
                    onPrintInventory = {
                        if (a4PrinterId.isBlank()) {
                            printError = "Выберите A4-принтер в сервисном меню"
                        } else {
                            printError = null
                            printMessage = "Опись отправлена на принтер"
                            scope.launch {
                                runCatching {
                                    ApiClient.envelopeApi(serverUrl).printInventory(envelope.id, a4PrinterId)
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
                                SwipeToDeleteDocRow(
                                    index = i + 1,
                                    doc = doc,
                                    onDelete = {
                                        scope.launch {
                                            sealMessage = null
                                            sealError = null
                                            runCatching {
                                                ApiClient.envelopeApi(serverUrl).deleteDocument(envelope.id, doc.id)
                                            }.onSuccess {
                                                onEnvelopeChanged(
                                                    envelope.copy(
                                                        documents = envelope.documents.filterNot { it.id == doc.id },
                                                    ),
                                                )
                                                sealMessage = "Документ удалён"
                                                playScanSound(context, success = true)
                                            }.onFailure { err ->
                                                sealError = apiErrorText(err)
                                                playScanSound(context, success = false)
                                            }
                                        }
                                    },
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
                        enabled = !isSealing,
                        modifier = Modifier.weight(1f).height(56.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                    ) {
                        Text("Запечатать", style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
    }
    if (isSealing) {
        BrandLoadingOverlay("Запечатываем конверт...")
    }
    } // Box

    if (showSealSignerSheet) {
        SelectionSheet(
            title = "Подписант № 2 (экспедитор)",
            desc = sealSignersError ?: "",
            options = sealSignersList,
            selectedId = "",
            onSelect = { selected ->
                showSealSignerSheet = false
                doSeal(selected.id)
            },
            onDismiss = { showSealSignerSheet = false },
        )
    }
}

@Composable
private fun RegisterTopBar(onBack: () -> Unit, title: String, subtitle: String? = null) {
    val compact = isCompactTsd()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(if (compact) 48.dp else 56.dp)
            .background(GradBlue)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(if (compact) 40.dp else 44.dp)) {
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
                style = if (compact) MaterialTheme.typography.bodyMedium else MaterialTheme.typography.titleMedium,
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
    onPrintLabel: () -> Unit,
    onPrintInventory: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val compact = isCompactTsd()
    Column(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(if (compact) 10.dp else 14.dp),
            verticalArrangement = Arrangement.spacedBy(if (compact) 8.dp else 12.dp),
        ) {
            if (printMessage != null) ScanFeedbackBanner(printMessage, isError = false)
            if (printError != null) ScanFeedbackBanner(printError, isError = true)
            SectionLabel("Печать")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                PrintActionButton(
                    text = "Этикетка ZPL",
                    onClick = onPrintLabel,
                    modifier = Modifier.weight(1f),
                )
                PrintActionButton(
                    text = "Опись A4",
                    onClick = onPrintInventory,
                    modifier = Modifier.weight(1f),
                )
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
private fun PrintActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Button(
        onClick = onClick,
        modifier = modifier.height(if (isCompactTsd()) 40.dp else 44.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(containerColor = SurfaceTint),
        elevation = ButtonDefaults.buttonElevation(0.dp),
        border = BorderStroke(1.dp, Color(0xFFC9DEF0)),
        contentPadding = PaddingValues(horizontal = 8.dp),
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_printer),
            contentDescription = null,
            tint = BrandBlue,
            modifier = Modifier.size(16.dp),
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text,
            style = MaterialTheme.typography.bodyMedium,
            color = BrandBlue,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun EnvelopeHero(
    envelope: EnvelopeDto,
    branchName: String,
    signerName: String,
) {
    val compact = isCompactTsd()
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(GradBlue)
            .padding(if (compact) 10.dp else 16.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(if (compact) 5.dp else 8.dp)) {
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
                style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.titleLarge,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(if (compact) 10.dp else 16.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
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
                EnvelopeHeaderDetails(
                    branchName = branchName,
                    signerName = signerName,
                    modifier = Modifier.weight(1f),
                )
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
    branchName: String,
    signerName: String,
) {
    val compact = isCompactTsd()
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(GradBlue)
            .padding(if (compact) 10.dp else 16.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(if (compact) 5.dp else 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(status = status, onDark = true)
                Spacer(modifier = Modifier.weight(1f))
            }
            Text(
                envelopeNumber,
                color = MaterialTheme.colorScheme.onPrimary,
                style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.titleLarge,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
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
                EnvelopeHeaderDetails(
                    branchName = branchName,
                    signerName = signerName,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun EnvelopeHeaderDetails(
    branchName: String,
    signerName: String,
    modifier: Modifier = Modifier,
) {
    val branchText = branchName.ifBlank { "Филиал не выбран" }
    val signerText = signerName.ifBlank { "Подписант не выбран" }
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            branchText,
            color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.92f),
            style = MaterialTheme.typography.labelMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            signerText,
            color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.68f),
            style = MaterialTheme.typography.labelSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
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

@OptIn(ExperimentalMaterial3Api::class)
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
    a4Printer: String,
    a4PrinterId: String,
    onBack: () -> Unit,
    onSaveSettings: (String, String, String, String, String, String, String, String, String) -> Unit,
    onLogout: () -> Unit,
) {
    var editableServerUrl by rememberSaveable(serverUrl) { mutableStateOf(serverUrl) }
    var editableBranch by rememberSaveable(branch) { mutableStateOf(branch) }
    var editableBranchId by rememberSaveable(branchId) { mutableStateOf(branchId) }
    var editableSigner by rememberSaveable(signer) { mutableStateOf(signer) }
    var editableSignerId by rememberSaveable(signerId) { mutableStateOf(signerId) }
    var editablePrinter by rememberSaveable(printer) { mutableStateOf(printer) }
    var editablePrinterId by rememberSaveable(printerId) { mutableStateOf(printerId) }
    var editableA4Printer by rememberSaveable(a4Printer) { mutableStateOf(a4Printer) }
    var editableA4PrinterId by rememberSaveable(a4PrinterId) { mutableStateOf(a4PrinterId) }
    var branches by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var signers by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var printers by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var a4Printers by remember { mutableStateOf<List<SelectOption>>(emptyList()) }
    var listError by remember { mutableStateOf<String?>(null) }
    var listsLoading by remember { mutableStateOf(false) }
    var showBranchSheet by remember { mutableStateOf(false) }
    var showSignerSheet by remember { mutableStateOf(false) }
    var showPrinterSheet by remember { mutableStateOf(false) }
    var showA4PrinterSheet by remember { mutableStateOf(false) }
    var showServerDialog by remember { mutableStateOf(false) }
    var showLogoutConfirm by remember { mutableStateOf(false) }
    var tempServerUrl by remember { mutableStateOf(editableServerUrl) }

    LaunchedEffect(serverUrl) {
        listsLoading = true
        listError = null
        runCatching {
            val api = ApiClient.settingsApi(serverUrl)
            val branchItems = api.branches().map { SelectOption(it.id, it.name) }
            val signerItems = api.signers().map { SelectOption(it.id, "${it.last_name} ${it.first_name}") }
            val printerItems = api.printers().items
            val zplPrinterItems = printerItems.filter { it.kind == "zpl" }.map { SelectOption(it.id, it.displayName()) }
            val a4PrinterItems = printerItems.filter { it.kind == "a4" }.map { SelectOption(it.id, it.displayName()) }
            ListsPayload(branchItems, signerItems, zplPrinterItems, a4PrinterItems)
        }.onSuccess { payload ->
            val branchItems = payload.branches
            val signerItems = payload.signers
            val printerItems = payload.zplPrinters
            val a4PrinterItems = payload.a4Printers
            branches = branchItems
            signers = signerItems
            printers = printerItems
            a4Printers = a4PrinterItems
        }.onFailure {
            listError = "Не удалось загрузить списки"
        }
        listsLoading = false
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
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
                ServiceSection("Учётная запись") {
                    ServiceRow(
                        icon = R.drawable.ic_circle_user,
                        title = "Оператор",
                        value = operator,
                        showChevron = false,
                    )
                    ServiceDivider()
                    ServiceRow(
                        icon = R.drawable.ic_log_out,
                        title = "Выйти",
                        titleColor = BrandRed,
                        onClick = { showLogoutConfirm = true },
                    )
                }
                ServiceSection("Подключение") {
                    ServiceRow(
                        icon = R.drawable.ic_settings,
                        title = "Адрес сервера",
                        value = editableServerUrl.ifBlank { "Не задан" },
                        onClick = {
                            tempServerUrl = editableServerUrl
                            showServerDialog = true
                        },
                    )
                }
                ServiceSection("Предпочтения отправки") {
                    ServiceRow(
                        icon = R.drawable.ic_building_2,
                        title = "Филиал отправки",
                        value = editableBranch.ifBlank { "Не выбран" },
                        onClick = { showBranchSheet = true },
                    )
                    ServiceDivider()
                    ServiceRow(
                        icon = R.drawable.ic_user_round,
                        title = "Подписант",
                        value = editableSigner.ifBlank { "Не выбран" },
                        onClick = { showSignerSheet = true },
                    )
                }
                ServiceSection("Печать") {
                    ServiceRow(
                        icon = R.drawable.ic_printer,
                        title = "ZPL-принтер",
                        value = editablePrinter.ifBlank { "Не выбран" },
                        onClick = { showPrinterSheet = true },
                    )
                    ServiceDivider()
                    ServiceRow(
                        icon = R.drawable.ic_printer,
                        title = "A4-принтер",
                        value = editableA4Printer.ifBlank { "Не выбран" },
                        onClick = { showA4PrinterSheet = true },
                    )
                }
                ServiceSection("Об устройстве") {
                    ServiceRow(
                        icon = R.drawable.ic_smartphone,
                        title = "ТСД",
                        value = android.os.Build.MODEL ?: "Android",
                        showChevron = false,
                    )
                    ServiceDivider()
                    ServiceRow(
                        icon = R.drawable.ic_info,
                        title = "Версия",
                        value = "v1.4.0",
                        showChevron = false,
                    )
                }
                if (listsLoading) {
                    Text("Загрузка...", style = MaterialTheme.typography.labelSmall, color = FgLabel, modifier = Modifier.padding(horizontal = 4.dp))
                }
                if (listError != null) {
                    Text(listError.orEmpty(), style = MaterialTheme.typography.labelSmall, color = BrandRed, modifier = Modifier.padding(horizontal = 4.dp))
                }
            }
            BottomBar {
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
                            editableA4PrinterId,
                            editableA4Printer.trim(),
                        )
                    },
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandBlue),
                ) {
                    Text("Сохранить", style = MaterialTheme.typography.titleMedium)
                }
            }
            ConnBanner(isOnline = isOnline)
        }
    }

    if (showBranchSheet) {
        SelectionSheet(
            title = "Филиал отправки",
            desc = "Подставится по умолчанию при создании конверта",
            options = branches,
            selectedId = editableBranchId,
            onSelect = { selected ->
                editableBranchId = selected.id
                editableBranch = selected.label
                showBranchSheet = false
            },
            onDismiss = { showBranchSheet = false },
        )
    }
    if (showSignerSheet) {
        SelectionSheet(
            title = "Подписант",
            options = signers,
            selectedId = editableSignerId,
            onSelect = { selected ->
                editableSignerId = selected.id
                editableSigner = selected.label
                showSignerSheet = false
            },
            onDismiss = { showSignerSheet = false },
        )
    }
    if (showPrinterSheet) {
        SelectionSheet(
            title = "ZPL-принтер",
            options = printers,
            selectedId = editablePrinterId,
            onSelect = { selected ->
                editablePrinterId = selected.id
                editablePrinter = selected.label
                showPrinterSheet = false
            },
            onDismiss = { showPrinterSheet = false },
        )
    }
    if (showA4PrinterSheet) {
        SelectionSheet(
            title = "A4-принтер",
            options = a4Printers,
            selectedId = editableA4PrinterId,
            onSelect = { selected ->
                editableA4PrinterId = selected.id
                editableA4Printer = selected.label
                showA4PrinterSheet = false
            },
            onDismiss = { showA4PrinterSheet = false },
        )
    }
    if (showServerDialog) {
        AlertDialog(
            onDismissRequest = { showServerDialog = false },
            title = { Text("Адрес сервера") },
            text = {
                OutlinedTextField(
                    value = tempServerUrl,
                    onValueChange = { tempServerUrl = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("URL") },
                    placeholder = { Text("http://127.0.0.1:8080") },
                )
            },
            confirmButton = {
                TextButton(onClick = { editableServerUrl = tempServerUrl.trim(); showServerDialog = false }) {
                    Text("Сохранить")
                }
            },
            dismissButton = {
                TextButton(onClick = { showServerDialog = false }) {
                    Text("Отмена")
                }
            },
        )
    }
    if (showLogoutConfirm) {
        AlertDialog(
            onDismissRequest = { showLogoutConfirm = false },
            title = { Text("Выход из системы") },
            text = { Text("Вы уверены, что хотите выйти из учётной записи?") },
            confirmButton = {
                TextButton(onClick = { showLogoutConfirm = false; onLogout() }) {
                    Text("Выйти", color = BrandRed)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutConfirm = false }) {
                    Text("Отмена")
                }
            },
        )
    }
}

data class SelectOption(
    val id: String,
    val label: String,
)

private data class ListsPayload(
    val branches: List<SelectOption>,
    val signers: List<SelectOption>,
    val zplPrinters: List<SelectOption>,
    val a4Printers: List<SelectOption>,
)

private fun PrinterDto.displayName(): String {
    val address = when {
        !share_name.isNullOrBlank() -> " · $share_name"
        !host.isNullOrBlank() && port != null -> " · $host:$port"
        else -> ""
    }
    return "$name$address"
}

@Composable
private fun ServiceTopBar(onBack: () -> Unit) {
    val compact = isCompactTsd()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(if (compact) 48.dp else 56.dp)
            .background(GradBlue)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(if (compact) 40.dp else 44.dp)) {
            Icon(
                painter = painterResource(R.drawable.ic_arrow_left),
                contentDescription = "Назад",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Text(
            text = "Сервисное меню",
            color = MaterialTheme.colorScheme.onPrimary,
            style = if (compact) MaterialTheme.typography.bodyMedium else MaterialTheme.typography.titleMedium,
        )
    }
}

@Composable
private fun ServiceSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionLabel(title)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
                .background(Color.White),
        ) {
            content()
        }
    }
}

@Composable
private fun ServiceRow(
    icon: Int,
    title: String,
    value: String = "",
    titleColor: Color = BrandInk,
    showChevron: Boolean = true,
    onClick: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            tint = FgLabel,
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = titleColor,
            )
            if (value.isNotEmpty()) {
                Text(
                    text = value,
                    style = MaterialTheme.typography.labelSmall,
                    color = FgMuted,
                )
            }
        }
        if (showChevron && onClick != null) {
            Icon(
                painter = painterResource(R.drawable.ic_chevron_right),
                contentDescription = null,
                tint = FgLabel,
                modifier = Modifier.size(16.dp),
            )
        }
    }
}

@Composable
private fun ServiceDivider() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(1.dp)
            .padding(start = 50.dp)
            .background(BorderLine),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SelectionSheet(
    title: String,
    desc: String = "",
    options: List<SelectOption>,
    selectedId: String,
    onSelect: (SelectOption) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 32.dp),
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, color = BrandInk)
                if (desc.isNotEmpty()) {
                    Spacer(Modifier.height(2.dp))
                    Text(desc, style = MaterialTheme.typography.labelSmall, color = FgMuted)
                }
            }
            HorizontalDivider(color = BorderLine)
            if (options.isEmpty()) {
                Text(
                    text = "Нет доступных вариантов",
                    style = MaterialTheme.typography.bodyMedium,
                    color = FgMuted,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 16.dp),
                )
            } else {
                options.forEach { option ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp)
                            .clickable { onSelect(option) }
                            .padding(horizontal = 16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = option.label,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium,
                            color = BrandInk,
                        )
                        if (option.id == selectedId) {
                            Icon(
                                painter = painterResource(R.drawable.ic_check),
                                contentDescription = null,
                                tint = BrandBlue,
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    }
                    if (option != options.last()) {
                        HorizontalDivider(
                            color = BorderSoft,
                            modifier = Modifier.padding(horizontal = 16.dp),
                        )
                    }
                }
            }
        }
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
        Text("v1.4.0", style = MaterialTheme.typography.labelSmall, color = FgLabel.copy(alpha = 0.55f))
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
    branchName: String,
    signerName: String,
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
                branchName = branchName,
                signerName = signerName,
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
                    BrandLoader(modifier = Modifier.size(34.dp))
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

@Composable
private fun BrandLoader(modifier: Modifier = Modifier) {
    var step by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(450L)
            step = (step + 1) % 8
        }
    }
    val infiniteTransition = rememberInfiniteTransition(label = "logo-pulse")
    val logoPulse by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.035f,
        animationSpec = infiniteRepeatable(tween(1800), RepeatMode.Reverse),
        label = "logo-scale",
    )
    val inactive = Color(0xFFD9E8F6)
    val segColors = (0..7).map { i ->
        when {
            i == step % 8 -> Color(0xFF1D71B8)
            i == (step + 3) % 8 -> Color(0xFFE4032E)
            i == (step + 6) % 8 -> Color(0xFF1B2848)
            else -> inactive
        }
    }
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            val radius = size.minDimension * 0.36f
            val strokeW = size.minDimension * 0.055f
            val arcSweep = 26f
            val sectorSize = 45f
            val gapHalf = (sectorSize - arcSweep) / 2f
            for (i in 0..7) {
                val startAngle = -90f + i * sectorSize + gapHalf
                drawArc(
                    color = segColors[i],
                    startAngle = startAngle,
                    sweepAngle = arcSweep,
                    useCenter = false,
                    topLeft = Offset(cx - radius, cy - radius),
                    size = Size(radius * 2f, radius * 2f),
                    style = Stroke(width = strokeW, cap = StrokeCap.Round),
                )
            }
        }
        Image(
            painter = painterResource(R.drawable.ic_launcher_foreground),
            contentDescription = null,
            modifier = Modifier
                .fillMaxSize(0.41f)
                .graphicsLayer {
                    scaleX = logoPulse
                    scaleY = logoPulse
                    alpha = 1f - ((logoPulse - 1f) / 0.035f * 0.08f)
                },
            colorFilter = ColorFilter.tint(Color(0xFF2C467E)),
        )
    }
}

@Composable
private fun BrandLoadingOverlay(label: String? = null) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BrandInk.copy(alpha = 0.75f))
            .clickable(enabled = false, onClick = {}),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            BrandLoader(modifier = Modifier.size(128.dp))
            if (label != null) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White,
                )
            }
        }
    }
}

@Composable
private fun SplashScreen() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White),
        contentAlignment = Alignment.Center,
    ) {
        Image(
            painter = painterResource(R.drawable.app_splash),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Fit,
        )
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
private fun SwipeToDeleteDocRow(
    index: Int,
    doc: DocumentDto,
    onDelete: () -> Unit,
) {
    val maxRevealPx = with(LocalDensity.current) { 72.dp.toPx() }
    var offsetX by remember(doc.id) { mutableFloatStateOf(0f) }

    Box(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .matchParentSize()
                .background(DangerBg)
                .padding(end = 8.dp),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(
                onClick = {
                    offsetX = 0f
                    onDelete()
                },
                modifier = Modifier.size(56.dp),
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_trash_2),
                    contentDescription = "Удалить",
                    tint = BrandRed,
                    modifier = Modifier.size(24.dp),
                )
            }
        }
        Box(
            modifier = Modifier
                .offset { IntOffset(offsetX.roundToInt(), 0) }
                .pointerInput(doc.id) {
                    detectHorizontalDragGestures(
                        onDragEnd = {
                            offsetX = if (offsetX < -maxRevealPx / 2f) -maxRevealPx else 0f
                        },
                        onDragCancel = {
                            offsetX = 0f
                        },
                        onHorizontalDrag = { change, dragAmount ->
                            change.consume()
                            offsetX = (offsetX + dragAmount).coerceIn(-maxRevealPx, 0f)
                        },
                    )
                },
        ) {
            DocRow(
                index = index,
                kind = doc.doc_kind,
                number = doc.doc_number,
                date = doc.doc_date.toDisplayDate(),
            )
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
) {
    val compact = isCompactTsd()
    val bg = when (scanned) {
        true -> SuccessBg
        false -> Color(0xFFFCE8E8)
        null -> Color.White
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(bg)
            .padding(horizontal = if (compact) 10.dp else 14.dp, vertical = if (compact) 7.dp else 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(if (compact) 7.dp else 10.dp),
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
                modifier = Modifier.size(if (compact) 12.dp else 13.dp),
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
                    style = if (compact) MaterialTheme.typography.labelMedium else MaterialTheme.typography.bodyMedium,
                    color = if (scanned == false) FgMuted else BrandInk,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
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
    val compact = isCompactTsd()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .drawBehind {
                drawLine(Color(0xFFDDE4EF), start = Offset(0f, 0f), end = Offset(size.width, 0f), strokeWidth = 1.dp.toPx())
            }
            .padding(horizontal = 12.dp, vertical = if (compact) 6.dp else 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        content()
    }
}

@Composable
private fun RecentEnvelopesBlock(
    envelopes: List<EnvelopeDto>,
    isLoading: Boolean,
    error: String?,
    onEnvelopeClick: (EnvelopeDto) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .border(1.dp, BorderSoft, RoundedCornerShape(10.dp))
            .background(Color.White),
    ) {
        when {
            isLoading && envelopes.isEmpty() -> RecentEmptyState("Загружаем последние конверты...")
            error != null && envelopes.isEmpty() -> RecentEmptyState(error)
            envelopes.isEmpty() -> RecentEmptyState("Конвертов пока нет", "Конверты появятся после регистрации")
            else -> {
                envelopes.forEachIndexed { index, envelope ->
                    if (index > 0) {
                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(BorderLine))
                    }
                    RecentEnvelopeRow(envelope = envelope, onClick = { onEnvelopeClick(envelope) })
                }
            }
        }
    }
}

@Composable
private fun RecentEmptyState(title: String, subtitle: String? = null) {
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
        Text(title, style = MaterialTheme.typography.titleMedium, color = BrandInk)
        if (subtitle != null) {
            Text(subtitle, style = MaterialTheme.typography.labelSmall, color = FgMuted)
        }
    }
}

@Composable
private fun RecentEnvelopeRow(envelope: EnvelopeDto, onClick: () -> Unit) {
    val (accent, bg, label) = recentStatusStyle(envelope.status)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            modifier = Modifier
                .size(42.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(bg),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_package_plus),
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(22.dp),
            )
        }
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(envelope.number, style = MaterialTheme.typography.bodyMedium, color = BrandInk, fontWeight = FontWeight.Bold)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(999.dp))
                        .background(bg)
                        .padding(horizontal = 7.dp, vertical = 2.dp),
                ) {
                    Text(label, style = MaterialTheme.typography.labelMedium, color = accent)
                }
                Text(recentEnvelopeMeta(envelope), style = MaterialTheme.typography.labelSmall, color = FgMuted)
            }
        }
        Icon(
            painter = painterResource(R.drawable.ic_chevron_right),
            contentDescription = null,
            tint = FgLabel,
            modifier = Modifier.size(20.dp),
        )
    }
}

private fun recentStatusStyle(status: String): Triple<Color, Color, String> {
    return when (status) {
        "draft" -> Triple(SuccessGreen, SuccessBg, "ЧЕРНОВИК")
        "sealed" -> Triple(WarningOrange, WarningBg, "ЗАПЕЧАТАН")
        "verified" -> Triple(SuccessGreen, SuccessBg, "СВЕРЕН")
        "verified_with_discrepancy" -> Triple(BrandRed, DangerBg, "С РАСХОЖДЕНИЕМ")
        else -> Triple(FgMuted, SurfaceAlt, status.uppercase())
    }
}

private fun recentEnvelopeMeta(envelope: EnvelopeDto): String {
    val count = envelope.documents.size
    val docText = "$count док."
    val timeText = runCatching {
        val parsed = java.time.OffsetDateTime.parse(envelope.created_at)
        val local = parsed.toLocalDateTime()
        val today = java.time.LocalDate.now()
        val day = when (local.toLocalDate()) {
            today -> "сегодня"
            today.minusDays(1) -> "вчера"
            else -> local.toLocalDate().toString()
        }
        "$day ${local.toLocalTime().toString().take(5)}"
    }.getOrElse {
        envelope.created_at.substringBefore(".").replace("T", " ").takeLast(16)
    }
    if (envelope.status == "verified_with_discrepancy") {
        val missing = envelope.documents.count { it.scanned_at_verification == null }
        return "$docText · $missing не найден"
    }
    return "$docText · $timeText"
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
            onOpenDraft = {},
            onVerifyEnvelopeStarted = {},
            onEnvelopeCreated = {},
        )
    }
}
