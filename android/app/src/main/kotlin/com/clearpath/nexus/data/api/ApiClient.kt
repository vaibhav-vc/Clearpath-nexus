package com.clearpath.nexus.data.api

import com.clearpath.nexus.BuildConfig
import io.github.jan.supabase.auth.auth
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Talks to the ClearPath FastAPI backend.
 *
 * Auth stays with Supabase: we lift the access token off the current session
 * and present it as a bearer token. The backend verifies it via JWKS. No
 * credentials are stored or minted here.
 */
object ApiClient {

    /** Set per build type in build.gradle.kts. Emulator host is 10.0.2.2. */
    private val baseUrl: String = BuildConfig.API_BASE_URL.trimEnd('/')

    private val json = Json {
        ignoreUnknownKeys = true   // backend may add fields; don't crash on them
        isLenient = true
        encodeDefaults = true
    }

    private val http = HttpClient(Android) {
        expectSuccess = true
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            requestTimeoutMillis = 15_000
            connectTimeoutMillis = 8_000
            socketTimeoutMillis = 15_000
        }
        defaultRequest { contentType(ContentType.Application.Json) }
    }

    /** Current Supabase access token, or null when signed out. */
    private suspend fun accessToken(): String? =
        runCatching { SupabaseClient.client.auth.currentSessionOrNull()?.accessToken }.getOrNull()

    private suspend fun requireToken(): String =
        accessToken() ?: throw NotAuthenticatedException()

    suspend fun getStations(): List<StationDto> =
        http.get("$baseUrl/planner/stations") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()

    suspend fun evaluateRoute(request: RouteEvaluateRequestDto): RouteEvaluateResponseDto =
        http.post("$baseUrl/planner/evaluate") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
            setBody(request)
        }.body()

    suspend fun suggestRoute(request: RouteSuggestRequestDto): RouteSuggestResponseDto =
        http.post("$baseUrl/planner/suggest") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
            setBody(request)
        }.body()

    suspend fun simulateThreat(request: ThreatSimulationRequestDto): ThreatSimulationResponseDto =
        http.post("$baseUrl/planner/simulate") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
            setBody(request)
        }.body()

    suspend fun getRouteHistory(): List<RouteHistoryDto> =
        http.get("$baseUrl/planner/routes") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()

    suspend fun dispatchRoute(routeId: String): RouteDispatchDto =
        http.post("$baseUrl/planner/routes/$routeId/dispatch") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()

    suspend fun getSchedules(): List<TrainScheduleDto> =
        http.get("$baseUrl/planner/schedules") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()

    suspend fun dispatchSchedule(scheduleId: String): TrainScheduleDto =
        http.post("$baseUrl/planner/schedules/$scheduleId/dispatch") {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()

    suspend fun portSyncStatus(
        portId: String,
        vesselId: String,
        trainArrivalHours: Double,
    ): PortSyncStatusDto =
        http.get(
            "$baseUrl/port/sync-status" +
                "?port_id=$portId&vessel_id=$vesselId&train_arrival_hours=$trainArrivalHours"
        ) {
            header(HttpHeaders.Authorization, "Bearer ${requireToken()}")
        }.body()
}

/** Thrown when a backend call is attempted with no Supabase session. */
class NotAuthenticatedException : IllegalStateException("No active Supabase session")
