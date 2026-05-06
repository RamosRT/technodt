package ru.technoavia.konverttrack.data.api

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

data class DocumentAddRequest(val barcode: String)

data class SealRequest(
    val signer_sender_id: String,
    val signer_receiver_id: String,
    val origin_branch_id: String,
    val destination_branch_id: String? = null,
    val notes: String? = null,
)

data class DocumentDto(
    val id: String,
    val doc_barcode: String,
    val doc_kind: String,
    val doc_number: String,
    val doc_date: String,
    val scanned_at_verification: String? = null,
)

data class EnvelopeDto(
    val id: String,
    val number: String,
    val barcode: String,
    val status: String,
    val created_at: String,
    val created_by: String,
    val documents: List<DocumentDto> = emptyList(),
)

data class VerifyScanRequest(val barcode: String)

data class VerifyScanResponse(
    val matched: Boolean,
    val doc_id: String? = null,
    val scanned_at: String? = null,
    val reason: String? = null,
)

data class VerifyFinishRequest(val force: Boolean = false)

data class VerifyFinishResponse(
    val status: String,
    val missing_docs: List<String> = emptyList(),
)

interface EnvelopeApi {
    @POST("api/envelopes")
    suspend fun createEnvelope(): EnvelopeDto

    @GET("api/envelopes/recent")
    suspend fun recentEnvelopes(@Query("limit") limit: Int = 5): List<EnvelopeDto>

    @GET("api/envelopes/by-barcode/{barcode}")
    suspend fun getByBarcode(@Path("barcode") barcode: String): EnvelopeDto

    @POST("api/envelopes/{envelopeId}/documents")
    suspend fun addDocument(
        @Path("envelopeId") envelopeId: String,
        @Body request: DocumentAddRequest,
    ): DocumentDto

    @DELETE("api/envelopes/{envelopeId}/documents/{documentId}")
    suspend fun deleteDocument(
        @Path("envelopeId") envelopeId: String,
        @Path("documentId") documentId: String,
    ): retrofit2.Response<Unit>

    @POST("api/envelopes/{envelopeId}/seal")
    suspend fun sealEnvelope(
        @Path("envelopeId") envelopeId: String,
        @Body request: SealRequest,
    ): EnvelopeDto

    @POST("api/envelopes/{envelopeId}/print/label/send")
    suspend fun printLabel(
        @Path("envelopeId") envelopeId: String,
        @retrofit2.http.Query("printer_id") printerId: String,
    ): retrofit2.Response<Unit>

    @POST("api/envelopes/{envelopeId}/print/inventory/send")
    suspend fun printInventory(
        @Path("envelopeId") envelopeId: String,
        @retrofit2.http.Query("printer_id") printerId: String,
    ): retrofit2.Response<Unit>

    @POST("api/envelopes/{envelopeId}/verify/start")
    suspend fun verifyStart(@Path("envelopeId") envelopeId: String): EnvelopeDto

    @POST("api/envelopes/{envelopeId}/verify/scan")
    suspend fun verifyScan(
        @Path("envelopeId") envelopeId: String,
        @Body request: VerifyScanRequest,
    ): VerifyScanResponse

    @POST("api/envelopes/{envelopeId}/verify/finish")
    suspend fun verifyFinish(
        @Path("envelopeId") envelopeId: String,
        @Body request: VerifyFinishRequest,
    ): VerifyFinishResponse
}
