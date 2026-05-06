package ru.technoavia.konverttrack.data.api

import retrofit2.http.Body
import retrofit2.http.POST

data class LoginRequest(
    val username: String,
    val password: String,
)

data class LoginResponse(
    val ok: Boolean,
    val operator: String,
    val assigned_zpl_printer_id: String?,
    val assigned_a4_printer_id: String?,
)

interface AuthApi {
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse
}
