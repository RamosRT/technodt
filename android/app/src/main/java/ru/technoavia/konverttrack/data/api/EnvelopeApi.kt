package ru.technoavia.konverttrack.data.api

import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path

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

interface EnvelopeApi {
    @POST("api/envelopes")
    suspend fun createEnvelope(): EnvelopeDto

    @POST("api/envelopes/{envelopeId}/documents")
    suspend fun addDocument(
        @Path("envelopeId") envelopeId: String,
        @Body request: DocumentAddRequest,
    ): DocumentDto

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
}
