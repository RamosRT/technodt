package ru.technoavia.konverttrack.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = BrandBlue,
    onPrimary = Color.White,
    secondary = BrandInk,
    onSecondary = Color.White,
    tertiary = BrandGreen,
    background = SurfaceBase,
    onBackground = BrandInk,
    surface = SurfaceCard,
    onSurface = BrandInk,
    error = BrandRed,
)

@Composable
fun KonvertTrackTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = AppTypography,
        content = content,
    )
}
