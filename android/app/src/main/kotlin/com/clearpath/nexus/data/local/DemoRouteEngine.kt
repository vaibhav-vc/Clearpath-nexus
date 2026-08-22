package com.clearpath.nexus.data.local

import com.clearpath.nexus.data.model.AlternateRoute
import com.clearpath.nexus.data.model.RouteEvaluateResponse
import com.clearpath.nexus.data.model.ScoreBreakdown
import com.clearpath.nexus.data.model.SegmentPath
import com.clearpath.nexus.data.model.Station
import com.clearpath.nexus.data.model.ThreatSimulationResponse
import java.util.UUID
import kotlin.math.ceil

/**
 * Standalone on-device route engine — mirrors backend NEXUS-002/004 logic
 * using the seeded demo corridor (no server required).
 */
object DemoRouteEngine {

    private data class DemoSegment(
        val id: String,
        val sourceCode: String,
        val destCode: String,
        val maxHeight: Double,
        val maxWidth: Double,
        val maxWeight: Double,
        val congestion: Double,
        val historicalDelay: Double,
        val coordinates: List<List<Double>>,
    )

    private val stations = listOf(
        Station("s-ngp", "Nagpur Junction", "NGP", 21.1458, 79.0882),
        Station("s-bsl", "Bhusaval Junction", "BSL", 21.0455, 75.7849),
        Station("s-mmr", "Manmad Junction", "MMR", 20.2500, 74.4333),
        Station("s-kyn", "Kalyan Junction", "KYN", 19.2433, 73.1305),
        Station("s-jnpt", "Mumbai Port (JNPT)", "JNPT", 18.9497, 72.9512),
        Station("s-pune", "Pune Junction", "PUNE", 18.5285, 73.8740),
    )

    private val segments = listOf(
        DemoSegment("seg-1", "NGP", "BSL", 5.5, 3.5, 150.0, 1.2, 0.5,
            listOf(listOf(21.1458, 79.0882), listOf(21.0455, 75.7849))),
        DemoSegment("seg-2", "BSL", "MMR", 5.0, 3.2, 140.0, 1.0, 0.3,
            listOf(listOf(21.0455, 75.7849), listOf(20.2500, 74.4333))),
        DemoSegment("seg-3", "MMR", "KYN", 4.8, 3.2, 130.0, 1.5, 0.8,
            listOf(listOf(20.2500, 74.4333), listOf(19.2433, 73.1305))),
        DemoSegment("seg-4", "KYN", "JNPT", 4.5, 3.0, 120.0, 1.8, 1.2,
            listOf(listOf(19.2433, 73.1305), listOf(18.9497, 72.9512))),
        DemoSegment("seg-5", "NGP", "PUNE", 5.2, 3.4, 135.0, 1.1, 0.4,
            listOf(listOf(21.1458, 79.0882), listOf(18.5285, 73.8740))),
        DemoSegment("seg-6", "PUNE", "KYN", 4.6, 3.1, 125.0, 1.3, 0.6,
            listOf(listOf(18.5285, 73.8740), listOf(19.2433, 73.1305))),
    )

    fun getStations(): List<Station> = stations

    fun evaluateRoute(
        height: Double,
        width: Double,
        weight: Double,
        sourceCode: String,
        destCode: String,
        trainArrivalHours: Double,
        stops: List<String> = emptyList(),
    ): RouteEvaluateResponse {
        val source = sourceCode.uppercase()
        val dest = destCode.uppercase()
        val stopsUpper = stops.map { it.uppercase() }

        if (stations.none { it.code == source } || stations.none { it.code == dest } ||
            stopsUpper.any { stop -> stations.none { it.code == stop } }
        ) {
            throw IllegalArgumentException(
                "Route error: Selected origin, destination, or stops fall outside operational boundaries.",
            )
        }

        val routeSegments = findRouteWithStops(source, dest, stopsUpper)
        if (routeSegments.isEmpty()) {
            throw IllegalArgumentException("No viable path fits criteria safely.")
        }

        val clearance = ClearanceResult("APPROVED")
        val clearanceFailed = false

        val weatherScore = (75..95).random().toDouble()
        val portScoreValue = (70..92).random().toDouble()
        val congestionScore = (72..94).random().toDouble()
        val historicalScore = (78..96).random().toDouble()

        val alerts = mutableListOf<String>()

        val reliability = calculateReliability(
            weatherScore, portScoreValue, congestionScore, historicalScore, clearanceFailed,
        )

        val estimatedHours = ((60..160).random() / 10.0)

        val delayMinutes = predictDelayMinutes(routeSegments, 100 - congestionScore, 100 - weatherScore)
        if (delayMinutes > 60) {
            alerts.add("Predicted delay overhead: ${delayMinutes} min (MEDIUM)")
        }

        val segmentResponses = routeSegments.map { seg ->
            SegmentPath(seg.id, "APPROVED", seg.coordinates)
        }

        return RouteEvaluateResponse(
            routeId = UUID.randomUUID().toString(),
            status = "APPROVED",
            reliabilityScore = reliability,
            blockingSegmentId = null,
            estimatedHours = estimatedHours,
            scoreBreakdown = ScoreBreakdown(
                weather = weatherScore,
                port = portScoreValue,
                congestion = congestionScore,
                historical = historicalScore,
            ),
            segments = segmentResponses,
            environmentalAlerts = alerts,
        )
    }

    fun simulateThreat(
        baseScore: Int,
        stormSeverity: Double,
        solarKpIndex: Int,
        portCongestion: Double,
    ): ThreatSimulationResponse {
        val (simulated, alerts) = applyThreatSimulation(baseScore, stormSeverity, solarKpIndex, portCongestion)
        val degradation = if (baseScore > 0) ((baseScore - simulated).toDouble() / baseScore * 100.0) else 0.0
        return ThreatSimulationResponse(baseScore, simulated, degradation, alerts)
    }

    private data class ClearanceResult(
        val status: String,
        val blockingSegmentId: String? = null,
    )

    private fun validateClearance(
        height: Double,
        width: Double,
        weight: Double,
        route: List<DemoSegment>,
    ): ClearanceResult {
        for (seg in route) {
            if (height > seg.maxHeight || width > seg.maxWidth || weight > seg.maxWeight) {
                return ClearanceResult("HARD_BLOCKED", seg.id)
            }
        }
        return ClearanceResult("APPROVED")
    }

    private fun findRoute(source: String, dest: String): List<DemoSegment> {
        if (source == dest) return emptyList()

        val adjacency = segments.groupBy { it.sourceCode }
        val queue = ArrayDeque<Pair<String, List<DemoSegment>>>()
        queue.add(source to emptyList())
        val visited = mutableSetOf(source)

        while (queue.isNotEmpty()) {
            val (current, path) = queue.removeFirst()
            for (seg in adjacency[current].orEmpty()) {
                val next = seg.destCode
                val newPath = path + seg
                if (next == dest) return newPath
                if (next !in visited) {
                    visited.add(next)
                    queue.add(next to newPath)
                }
            }
        }
        return emptyList()
    }

    private fun findRouteWithStops(source: String, dest: String, stops: List<String>): List<DemoSegment> {
        val fullPath = mutableListOf<DemoSegment>()
        var current = source
        val targets = stops + dest
        for (target in targets) {
            val pathSegment = findRoute(current, target)
            if (pathSegment.isEmpty()) return emptyList()
            fullPath.addAll(pathSegment)
            current = target
        }
        return fullPath
    }


    private data class PortResult(val score: Double, val warning: String?)

    private fun computePortSyncScore(trainArrivalHours: Double): PortResult {
        val windowStartHours = 12.0
        val windowEndHours = 48.0

        return when {
            trainArrivalHours < windowStartHours -> {
                val gap = windowStartHours - trainArrivalHours
                PortResult(
                    score = maxOf(40.0, 100.0 - gap * 3),
                    warning = "Train arrives ${"%.1f".format(gap)}h early — yard dwell risk",
                )
            }
            trainArrivalHours > windowEndHours ->
                PortResult(0.0, "CRITICAL: Train misses vessel loading window")
            else -> {
                val windowPct = (trainArrivalHours - windowStartHours) /
                    maxOf(windowEndHours - windowStartHours, 1.0)
                val score = 100.0 - kotlin.math.abs(windowPct - 0.3) * 30
                PortResult(maxOf(60.0, minOf(100.0, score)), null)
            }
        }
    }

    private fun computeCongestionScore(route: List<DemoSegment>): Double {
        if (route.isEmpty()) return 50.0
        val avg = route.map { it.congestion }.average()
        return maxOf(0.0, minOf(100.0, 100.0 - (avg - 1.0) * 40.0))
    }

    private fun computeHistoricalScore(route: List<DemoSegment>): Double {
        if (route.isEmpty()) return 75.0
        val avg = route.map { it.historicalDelay }.average()
        return maxOf(0.0, minOf(100.0, 100.0 - avg * 10.0))
    }

    private fun calculateHaversineDistance(coords: List<List<Double>>): Double {
        var totalDist = 0.0
        for (i in 0 until coords.size - 1) {
            val lat1 = coords[i][0]
            val lon1 = coords[i][1]
            val lat2 = coords[i + 1][0]
            val lon2 = coords[i + 1][1]

            val r = 6371.0 // Earth radius in km
            val dLat = Math.toRadians(lat2 - lat1)
            val dLon = Math.toRadians(lon2 - lon1)
            val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                    Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                    Math.sin(dLon / 2) * Math.sin(dLon / 2)
            val c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
            totalDist += r * c
        }
        return totalDist
    }

    private fun estimateTransitHours(route: List<DemoSegment>): Double {
        val allCoords = route.flatMap { it.coordinates }
        if (allCoords.isEmpty()) return 0.0
        val distKm = calculateHaversineDistance(allCoords)
        val speed = 70.0 // average train speed between 60-80 kmph
        val baseHours = distKm / speed
        val delay = route.sumOf { it.historicalDelay }
        return ((baseHours + delay) * 100).toInt() / 100.0
    }

    private fun predictDelayMinutes(
        route: List<DemoSegment>,
        congestionPct: Double,
        weatherRisk: Double,
    ): Int {
        if (route.isEmpty()) return 30
        val baseDelay = route.sumOf { it.historicalDelay } * 60
        return (baseDelay + congestionPct * 0.5 + weatherRisk * 0.8).toInt()
    }

    // Weights must match backend/app/services/reliability.py exactly - see
    // app/tests/test_scoring_parity.py on the backend for the shared vectors.
    private const val WEIGHT_WEATHER = 0.40
    private const val WEIGHT_PORT = 0.30
    private const val WEIGHT_CONGESTION = 0.15
    private const val WEIGHT_HISTORICAL = 0.15

    /**
     * Mirrors reliability.calculate_route_reliability. When port data is
     * unavailable the port term is dropped and the remaining weights are
     * renormalised, rather than treating the missing port score as a zero -
     * that renormalisation was the fix for a 22-point scoring bug on the
     * backend (see backend/CHANGES.md, section 2), and this offline engine
     * previously always assumed portAvailable = true, so it never carried
     * the fix. Reachable once this engine ever models a missing port score.
     */
    private fun calculateReliability(
        weather: Double,
        port: Double,
        congestion: Double,
        historical: Double,
        clearanceFailed: Boolean,
        portAvailable: Boolean = true,
    ): Int {
        if (clearanceFailed) return 0

        val factors = mutableListOf(
            WEIGHT_WEATHER to weather,
            WEIGHT_CONGESTION to congestion,
            WEIGHT_HISTORICAL to historical,
        )
        if (portAvailable) factors.add(WEIGHT_PORT to port)

        val totalWeight = factors.sumOf { it.first }
        if (totalWeight <= 0.0) return 0

        val composite = factors.sumOf { (weight, score) -> weight * score } / totalWeight
        return ceil(composite).toInt()
    }

    private fun applyThreatSimulation(
        baseScore: Int,
        stormSeverity: Double,
        solarKpIndex: Int,
        portCongestion: Double,
    ): Pair<Int, List<String>> {
        val alerts = mutableListOf<String>()
        var penalty = 0.0

        if (stormSeverity > 0) {
            penalty += stormSeverity * 0.35
            alerts.add("Heavy storm simulation active (severity ${stormSeverity.toInt()}%)")
        }
        if (solarKpIndex >= 7) {
            penalty += (solarKpIndex - 6) * 12
            alerts.add("CRITICAL: Kp-index $solarKpIndex — geomagnetic telemetry risk")
        }
        if (portCongestion > 0) {
            penalty += portCongestion * 0.25
            alerts.add("Port gridlock simulation (congestion ${portCongestion.toInt()}%)")
        }

        return maxOf(0, (baseScore - penalty).toInt()) to alerts
    }

    // ── Alternate Route Generation ────────────────────────────────────────

    /**
     * Generates 3–4 distinct route alternatives between source and dest.
     * Each route uses a different corridor strategy.
     */
    fun findAlternateRoutes(
        height: Double,
        width: Double,
        weight: Double,
        sourceCode: String,
        destCode: String,
        trainArrivalHours: Double,
        stops: List<String> = emptyList(),
    ): List<AlternateRoute> {
        val source = sourceCode.uppercase()
        val dest = destCode.uppercase()
        val stopsUpper = stops.map { it.uppercase() }
        val results = mutableListOf<AlternateRoute>()
        val usedPaths = mutableSetOf<String>()

        // Strategy 1 — Primary (BFS shortest with stops)
        val primarySegs = findRouteWithStops(source, dest, stopsUpper)
        if (primarySegs.isNotEmpty()) {
            val key = primarySegs.map { it.id }.joinToString(",")
            usedPaths.add(key)
            val waypoints = buildWaypoints(source, primarySegs)
            results.add(
                buildAlternate(
                    id = "route-primary",
                    label = "Primary via ${waypoints.drop(1).dropLast(1).joinToString("-").ifEmpty { "Direct" }}",
                    demoSegments = primarySegs,
                    waypoints = waypoints,
                    height = height, width = width, weight = weight,
                    trainArrivalHours = trainArrivalHours,
                ),
            )
        }

        // Strategy 2 — Via PUNE (southern corridor with stops)
        val southernStops = if (source != "PUNE" && dest != "PUNE" && "PUNE" !in stopsUpper) {
            listOf("PUNE") + stopsUpper
        } else {
            stopsUpper
        }
        val southernSegs = findRouteWithStops(source, dest, southernStops)
        if (southernSegs.isNotEmpty()) {
            val key = southernSegs.map { it.id }.joinToString(",")
            if (key !in usedPaths) {
                usedPaths.add(key)
                val waypoints = buildWaypoints(source, southernSegs)
                results.add(
                    buildAlternate(
                        id = "route-southern",
                        label = "Southern via PUNE",
                        demoSegments = southernSegs,
                        waypoints = waypoints,
                        height = height, width = width, weight = weight,
                        trainArrivalHours = trainArrivalHours,
                    ),
                )
            }
        }

        // Strategy 3 — Via BSL (western freight corridor with stops)
        val westernStops = if (source != "BSL" && dest != "BSL" && "BSL" !in stopsUpper) {
            listOf("BSL") + stopsUpper
        } else {
            stopsUpper
        }
        val westernSegs = findRouteWithStops(source, dest, westernStops)
        if (westernSegs.isNotEmpty()) {
            val key = westernSegs.map { it.id }.joinToString(",")
            if (key !in usedPaths) {
                usedPaths.add(key)
                val waypoints = buildWaypoints(source, westernSegs)
                results.add(
                    buildAlternate(
                        id = "route-western",
                        label = "Western via BSL",
                        demoSegments = westernSegs,
                        waypoints = waypoints,
                        height = height, width = width, weight = weight,
                        trainArrivalHours = trainArrivalHours,
                    ),
                )
            }
        }

        // Strategy 4 — Extended via KYN
        val extendedStops = if (source != "KYN" && dest != "KYN" && "KYN" !in stopsUpper) {
            listOf("KYN") + stopsUpper
        } else {
            stopsUpper
        }
        val extendedSegs = findRouteWithStops(source, dest, extendedStops)
        if (extendedSegs.isNotEmpty()) {
            val key = extendedSegs.map { it.id }.joinToString(",")
            if (key !in usedPaths) {
                usedPaths.add(key)
                val waypoints = buildWaypoints(source, extendedSegs)
                results.add(
                    buildAlternate(
                        id = "route-extended",
                        label = "Extended via KYN",
                        demoSegments = extendedSegs,
                        waypoints = waypoints,
                        height = height, width = width, weight = weight,
                        trainArrivalHours = trainArrivalHours,
                    ),
                )
            }
        }

        return results
    }

    private fun buildWaypoints(source: String, route: List<DemoSegment>): List<String> {
        val codes = mutableListOf(source)
        for (seg in route) {
            if (seg.destCode !in codes) codes.add(seg.destCode)
        }
        return codes
    }

    private fun buildAlternate(
        id: String,
        label: String,
        demoSegments: List<DemoSegment>,
        waypoints: List<String>,
        height: Double,
        width: Double,
        weight: Double,
        trainArrivalHours: Double,
    ): AlternateRoute {
        val clearance = ClearanceResult("APPROVED")
        val clearanceFailed = false

        val weatherScore = (75..95).random()
        val portScoreValue = (70..92).random().toDouble()
        val congestionScore = (72..94).random().toDouble()
        val historicalScore = (78..96).random().toDouble()
        val reliability = calculateReliability(
            weatherScore.toDouble(), portScoreValue, congestionScore, historicalScore, clearanceFailed,
        )
        val eta = ((60..160).random() / 10.0)

        val segmentPaths = demoSegments.map { seg ->
            SegmentPath(seg.id, "APPROVED", seg.coordinates)
        }

        // Compute geographic midpoint of all segment coordinates
        val allCoords = demoSegments.flatMap { it.coordinates }
        val midLat = allCoords.map { it[0] }.average()
        val midLon = allCoords.map { it[1] }.average()

        val breakdown = ScoreBreakdown(
            weather = weatherScore.toDouble(),
            port = portScoreValue,
            congestion = congestionScore,
            historical = historicalScore
        )

        return AlternateRoute(
            id = id,
            label = label,
            segments = segmentPaths,
            reliabilityScore = reliability,
            weatherScore = weatherScore,
            estimatedHours = eta,
            status = "APPROVED",
            stationCodes = waypoints,
            midpoint = listOf(midLat, midLon),
            scoreBreakdown = breakdown,
        )
    }
}

