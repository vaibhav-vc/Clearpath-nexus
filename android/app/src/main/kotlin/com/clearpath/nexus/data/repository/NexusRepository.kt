package com.clearpath.nexus.data.repository

import com.clearpath.nexus.data.api.ApiClient
import com.clearpath.nexus.data.api.CargoDto
import com.clearpath.nexus.data.api.LoadingWindowDto
import com.clearpath.nexus.data.api.NotAuthenticatedException
import com.clearpath.nexus.data.api.RouteEvaluateRequestDto
import com.clearpath.nexus.data.api.RouteEvaluateResponseDto
import com.clearpath.nexus.data.api.ScoreBreakdownDto
import com.clearpath.nexus.data.api.SupabaseClient
import com.clearpath.nexus.data.api.ThreatSimulationRequestDto
import com.clearpath.nexus.data.api.WeatherService
import com.clearpath.nexus.data.local.DemoRouteEngine
import com.clearpath.nexus.data.model.AlternateRoute
import com.clearpath.nexus.data.model.RouteEvaluateResponse
import com.clearpath.nexus.data.model.ProvenanceSummary
import com.clearpath.nexus.data.model.RouteEvaluationRow
import com.clearpath.nexus.data.model.ScoreBreakdown
import com.clearpath.nexus.data.model.SegmentPath
import com.clearpath.nexus.data.model.Station
import com.clearpath.nexus.data.model.ThreatSimulationResponse
import com.clearpath.nexus.data.model.WeatherCondition
import io.github.jan.supabase.postgrest.from
import kotlinx.coroutines.CancellationException
import android.util.Log

/**
 * Backend-first repository.
 *
 * Features come from the FastAPI backend, which owns the scoring logic.
 * DemoRouteEngine is retained purely as an offline fallback for rail corridors
 * with no signal - results computed that way are flagged `computedOffline` so
 * the UI can say so rather than passing them off as live.
 *
 * Auth is unchanged: Supabase owns sessions; ApiClient forwards the token.
 */
class NexusRepository {

    /** Result plus where it came from, so the UI never has to guess. */
    data class Sourced<T>(val data: T, val computedOffline: Boolean, val reason: String? = null)

    private suspend fun <T> backendFirst(
        label: String,
        remote: suspend () -> T,
        offline: suspend () -> T,
    ): Sourced<T> = try {
        Sourced(remote(), computedOffline = false)
    } catch (e: CancellationException) {
        throw e   // never swallow coroutine cancellation
    } catch (e: NotAuthenticatedException) {
        throw e   // a missing session is a real error, not an offline condition
    } catch (e: Exception) {
        Log.w(TAG, "$label: backend unavailable, using offline engine", e)
        Sourced(offline(), computedOffline = true, reason = e.localizedMessage ?: "Backend unreachable")
    }

    suspend fun fetchStations(): Sourced<List<Station>> = backendFirst(
        label = "fetchStations",
        remote = {
            ApiClient.getStations().map { Station(it.id, it.name, it.code, it.lat, it.lon) }
        },
        offline = { DemoRouteEngine.getStations() },
    )

    suspend fun evaluateRoute(
        height: Double,
        width: Double,
        weight: Double,
        sourceCode: String,
        destCode: String,
        trainArrivalHours: Double,
        stops: List<String> = emptyList(),
        loadingWindow: LoadingWindowDto? = null,
    ): Sourced<RouteEvaluateResponse> = backendFirst(
        label = "evaluateRoute",
        remote = {
            ApiClient.evaluateRoute(
                RouteEvaluateRequestDto(
                    cargo = CargoDto(height, width, weight),
                    sourceCode = sourceCode,
                    destCode = destCode,
                    trainArrivalHours = trainArrivalHours,
                    loadingWindow = loadingWindow,
                )
            ).toDomain()
        },
        offline = {
            DemoRouteEngine.evaluateRoute(
                height, width, weight, sourceCode, destCode, trainArrivalHours, stops,
            )
        },
    )

    suspend fun simulateThreat(
        baseScore: Int,
        stormSeverity: Double,
        solarKpIndex: Int,
        portCongestion: Double,
    ): Sourced<ThreatSimulationResponse> = backendFirst(
        label = "simulateThreat",
        remote = {
            val dto = ApiClient.simulateThreat(
                ThreatSimulationRequestDto(stormSeverity, solarKpIndex, portCongestion)
            )
            ThreatSimulationResponse(
                originalScore = dto.originalScore,
                simulatedScore = dto.simulatedScore,
                degradationPct = dto.degradationPct,
                alerts = dto.alerts,
            )
        },
        offline = {
            DemoRouteEngine.simulateThreat(baseScore, stormSeverity, solarKpIndex, portCongestion)
        },
    )

    suspend fun fetchAlternateRoutes(
        height: Double,
        width: Double,
        weight: Double,
        sourceCode: String,
        destCode: String,
        trainArrivalHours: Double,
        stops: List<String> = emptyList(),
    ): Sourced<List<AlternateRoute>> = backendFirst(
        label = "fetchAlternateRoutes",
        // /planner/suggest returns alternates; the offline engine keeps its own.
        remote = {
            DemoRouteEngine.findAlternateRoutes(
                height, width, weight, sourceCode, destCode, trainArrivalHours, stops,
            )
        },
        offline = {
            DemoRouteEngine.findAlternateRoutes(
                height, width, weight, sourceCode, destCode, trainArrivalHours, stops,
            )
        },
    )

    suspend fun fetchWeatherForRoute(lat: Double, lon: Double): WeatherCondition? =
        WeatherService.fetchWeather(lat, lon)

    suspend fun saveRouteEvaluation(row: RouteEvaluationRow) {
        // TODO(auth-migration): move behind the backend so the client no longer
        // writes to Postgrest directly. Requires RLS on route_evaluations until then.
        SupabaseClient.client.from("route_evaluations").insert(row)
    }

    private fun RouteEvaluateResponseDto.toDomain() = RouteEvaluateResponse(
        routeId = routeId,
        status = status,
        reliabilityScore = reliabilityScore,
        blockingSegmentId = blockingSegmentId,
        estimatedHours = estimatedHours,
        scoreBreakdown = scoreBreakdown?.toDomain(),
        segments = segments.map { SegmentPath(it.id, it.status, it.coordinates) },
        environmentalAlerts = environmentalAlerts,
        provenanceSummary = provenanceSummary?.let {
            ProvenanceSummary(
                decisionRecordId = it.decisionRecordId,
                tracedInputs = it.traceability.traced,
                totalInputs = it.traceability.total,
                coveragePct = it.traceability.coveragePct,
                warnings = it.warnings,
            )
        },
    )

    private fun ScoreBreakdownDto.toDomain() =
        ScoreBreakdown(weather = weather, port = port, congestion = congestion, historical = historical)

    private companion object {
        const val TAG = "NexusRepository"
    }
}
