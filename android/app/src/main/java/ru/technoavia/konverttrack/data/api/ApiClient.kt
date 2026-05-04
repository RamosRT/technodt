package ru.technoavia.konverttrack.data.api

import okhttp3.OkHttpClient
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiClient {
    private val cookieJar = MemoryCookieJar()
    private val client: OkHttpClient by lazy {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .addInterceptor(logging)
            .build()
    }

    fun authApi(serverUrl: String): AuthApi {
        return retrofit(serverUrl).create(AuthApi::class.java)
    }

    fun settingsApi(serverUrl: String): SettingsApi {
        return retrofit(serverUrl).create(SettingsApi::class.java)
    }

    fun envelopeApi(serverUrl: String): EnvelopeApi {
        return retrofit(serverUrl).create(EnvelopeApi::class.java)
    }

    fun clearCookies() {
        cookieJar.clear()
    }

    private fun retrofit(serverUrl: String): Retrofit {
        return Retrofit.Builder()
            .baseUrl(normalizeBaseUrl(serverUrl))
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    private fun normalizeBaseUrl(raw: String): String {
        val trimmed = raw.trim()
        val withScheme = when {
            trimmed.startsWith("http://") || trimmed.startsWith("https://") -> trimmed
            else -> "http://$trimmed"
        }
        return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
    }
}

private class MemoryCookieJar : CookieJar {
    private val cookies = mutableMapOf<String, List<Cookie>>()

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        this.cookies[url.host] = cookies
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        return cookies[url.host].orEmpty()
    }

    fun clear() {
        cookies.clear()
    }
}
