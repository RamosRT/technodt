package ru.technoavia.konverttrack.data.api

import retrofit2.http.GET

data class BranchDto(
    val id: String,
    val name: String,
    val is_active: Boolean,
)

data class SignerDto(
    val id: String,
    val last_name: String,
    val first_name: String,
    val is_active: Boolean,
)

data class PrinterDto(
    val id: String,
    val name: String,
    val kind: String,
    val host: String?,
    val port: Int?,
    val dpi: Int?,
)

data class PrinterListResponse(
    val items: List<PrinterDto>,
)

interface SettingsApi {
    @GET("api/branches")
    suspend fun branches(): List<BranchDto>

    @GET("api/signers")
    suspend fun signers(): List<SignerDto>

    @GET("api/printers")
    suspend fun printers(): PrinterListResponse
}
