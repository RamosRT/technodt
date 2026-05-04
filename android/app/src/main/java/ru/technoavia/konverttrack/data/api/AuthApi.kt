package ru.technoavia.konverttrack.data.api

import retrofit2.http.Body
import retrofit2.http.POST

data class LoginRequest(val name: String)

data class LoginResponse(
    val ok: Boolean,
    val operator: String,
)

interface AuthApi {
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse
}
