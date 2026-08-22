package com.clearpath.nexus.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clearpath.nexus.data.api.WeatherService
import com.clearpath.nexus.data.model.AlternateRoute
import com.clearpath.nexus.data.model.ScoreBreakdown
import com.clearpath.nexus.data.repository.NexusRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class RouteSelectionUiState(
    val routes: List<AlternateRoute> = emptyList(),
    val selectedRouteId: String? = null,
    val isLoading: Boolean = true,
    val isLoadingWeather: Boolean = false,
    val weatherError: String? = null,
)

class RouteSelectionViewModel(
    private val repository: NexusRepository = NexusRepository(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(RouteSelectionUiState())
    val uiState: StateFlow<RouteSelectionUiState> = _uiState.asStateFlow()

    fun loadRoutes(
        height: Double,
        width: Double,
        weight: Double,
        sourceCode: String,
        destCode: String,
        trainArrivalHours: Double,
        stops: List<String> = emptyList(),
    ) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }

            try {
                val routes = repository.fetchAlternateRoutes(
                    height, width, weight, sourceCode, destCode, trainArrivalHours, stops,
                ).data

                // Auto-select the first route
                val firstId = routes.firstOrNull()?.id
                _uiState.update {
                    it.copy(
                        routes = routes,
                        selectedRouteId = firstId,
                        isLoading = false,
                        isLoadingWeather = true,
                    )
                }

                // Fetch weather and OSRM route geometry concurrently for all routes
                val updatedRoutesDeferred = routes.map { route ->
                    async {
                        // 1. Fetch weather condition
                        val condition = repository.fetchWeatherForRoute(
                            route.midpoint[0], route.midpoint[1],
                        )
                        val weatherScore = WeatherService.weatherToScore(condition)

                        // 2. Fetch OSRM geometry for all segments in this route
                        val updatedSegments = route.segments.map { segment ->
                            val first = segment.coordinates.firstOrNull()
                            val last = segment.coordinates.lastOrNull()
                            if (first != null && last != null) {
                                val lat1 = first[0]
                                val lon1 = first[1]
                                val lat2 = last[0]
                                val lon2 = last[1]
                                val osrmGeometry = fetchSegmentGeometry(lat1, lon1, lat2, lon2)
                                if (osrmGeometry.isNotEmpty()) {
                                    segment.copy(coordinates = osrmGeometry)
                                } else {
                                    segment
                                }
                            } else {
                                segment
                            }
                        }

                        val updatedBreakdown = (route.scoreBreakdown ?: ScoreBreakdown(
                            weather = weatherScore.toDouble(),
                            port = 85.0,
                            congestion = 72.0,
                            historical = 90.0
                        )).copy(weather = weatherScore.toDouble())

                        val updatedReliability = if (route.status == "HARD_BLOCKED") {
                            0
                        } else {
                            val composite = 0.40 * updatedBreakdown.weather + 0.30 * updatedBreakdown.port + 0.15 * updatedBreakdown.congestion + 0.15 * updatedBreakdown.historical
                            kotlin.math.ceil(composite).toInt().coerceIn(0, 100)
                        }

                        route.copy(
                            weatherCondition = condition,
                            weatherScore = weatherScore,
                            reliabilityScore = updatedReliability,
                            segments = updatedSegments,
                            scoreBreakdown = updatedBreakdown
                        )
                    }
                }

                val updatedRoutes = updatedRoutesDeferred.awaitAll()

                _uiState.update {
                    it.copy(
                        routes = updatedRoutes,
                        isLoadingWeather = false,
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isLoadingWeather = false,
                        weatherError = e.message,
                    )
                }
            }
        }
    }

    private suspend fun fetchSegmentGeometry(lat1: Double, lon1: Double, lat2: Double, lon2: Double): List<List<Double>> =
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            try {
                val url = java.net.URL("https://router.project-osrm.org/route/v1/driving/$lon1,$lat1;$lon2,$lat2?overview=full&geometries=geojson")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.connectTimeout = 8_000
                conn.readTimeout = 8_000
                conn.requestMethod = "GET"
                conn.setRequestProperty("User-Agent", "ClearPathNexus/1.0")

                if (conn.responseCode != 200) return@withContext emptyList()

                val body = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()

                val root = org.json.JSONObject(body)
                val routesJson = root.getJSONArray("routes")
                if (routesJson.length() == 0) return@withContext emptyList()

                val geom = routesJson.getJSONObject(0).getJSONObject("geometry")
                val coords = geom.getJSONArray("coordinates")
                val points = mutableListOf<List<Double>>()
                for (i in 0 until coords.length()) {
                    val coord = coords.getJSONArray(i)
                    val lon = coord.getDouble(0)
                    val lat = coord.getDouble(1)
                    points.add(listOf(lat, lon))
                }
                points
            } catch (e: Exception) {
                e.printStackTrace()
                emptyList()
            }
        }

    fun onRouteSelected(routeId: String) {
        _uiState.update { it.copy(selectedRouteId = routeId) }
    }

    fun getSelectedRoute(): AlternateRoute? {
        val state = _uiState.value
        return state.routes.find { it.id == state.selectedRouteId }
    }
}
