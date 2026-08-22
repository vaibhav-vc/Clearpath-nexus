package com.clearpath.nexus.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clearpath.nexus.data.api.LoadingWindowDto
import com.clearpath.nexus.data.api.SupabaseClient
import com.clearpath.nexus.data.api.WeatherService
import com.clearpath.nexus.data.model.EnvironmentalZone
import com.clearpath.nexus.data.model.RouteEvaluateResponse
import com.clearpath.nexus.data.model.RouteEvaluationRow
import com.clearpath.nexus.data.model.LoadProfile
import com.clearpath.nexus.data.model.ScoreBreakdown
import com.clearpath.nexus.data.model.Station
import com.clearpath.nexus.data.repository.NexusRepository
import io.github.jan.supabase.auth.auth
import kotlinx.serialization.encodeToString
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

data class DashboardUiState(
    val stations: List<Station> = emptyList(),
    val height: String = "4.8",
    val width: String = "3.2",
    val weight: String = "120",
    val sourceCode: String = "NGP",
    val destCode: String = "JNPT",
    val trainHours: String = "24",
    val useBerthWindow: Boolean = false,
    val berthStartHours: String = "12",
    val berthEndHours: String = "48",
    val isLoading: Boolean = false,
    val error: String? = null,
    val result: RouteEvaluateResponse? = null,
    val stormSeverity: Float = 0f,
    val solarKp: Float = 2f,
    val portCongestion: Float = 0f,
    val simLoading: Boolean = false,
    val simulatedScore: Int? = null,
    val simAlerts: List<String> = emptyList(),
    val selectedTab: DashboardTab = DashboardTab.CONFIGURE,
    val confirmedRouteLabel: String? = null,
    val confirmedRouteId: String? = null,
    val alternateRoutes: List<com.clearpath.nexus.data.model.AlternateRoute> = emptyList(),
    val stops: List<String> = emptyList(),
    val environmentalZones: List<EnvironmentalZone> = listOf(
        EnvironmentalZone(
            id = "dust-west",
            type = "dust",
            coordinates = listOf(
                listOf(21.5, 74.0),
                listOf(21.0, 75.5),
                listOf(20.0, 75.0),
                listOf(20.5, 73.5),
            ),
        ),
    ),
    val isSimulationMode: Boolean = false,
    val estimatedTotalHours: Float? = null,
    val loadProfiles: List<LoadProfile> = emptyList(),
    val selectedProfileId: String? = null,
)

enum class DashboardTab {
    CONFIGURE,
    ROUTE_SELECTION,
    MAP,
    TELEMETRY,
    SCHEDULE,
    HISTORY,
    LOADS,
    USER,
}

class DashboardViewModel(
    private val repository: NexusRepository = NexusRepository(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        loadStations()
    }

    fun onHeightChange(value: String) = _uiState.update { it.copy(height = value) }
    fun onWidthChange(value: String) = _uiState.update { it.copy(width = value) }
    fun onWeightChange(value: String) = _uiState.update { it.copy(weight = value) }
    fun onSourceChange(value: String) = _uiState.update { it.copy(sourceCode = value) }
    fun onDestChange(value: String) = _uiState.update { it.copy(destCode = value) }
    fun onTrainHoursChange(value: String) = _uiState.update { it.copy(trainHours = value) }
    fun onUseBerthWindowChange(value: Boolean) = _uiState.update { it.copy(useBerthWindow = value) }
    fun onBerthStartHoursChange(value: String) = _uiState.update { it.copy(berthStartHours = value) }
    fun onBerthEndHoursChange(value: String) = _uiState.update { it.copy(berthEndHours = value) }
    fun onStormChange(value: Float) = _uiState.update { it.copy(stormSeverity = value) }
    fun onSolarChange(value: Float) = _uiState.update { it.copy(solarKp = value) }
    fun onPortChange(value: Float) = _uiState.update { it.copy(portCongestion = value) }
    fun onTabSelected(tab: DashboardTab) = _uiState.update { it.copy(selectedTab = tab) }
    fun onStopsChange(value: List<String>) = _uiState.update { it.copy(stops = value) }

    private fun loadStations() {
        viewModelScope.launch {
            val stations = repository.fetchStations().data
            _uiState.update { it.copy(stations = stations) }
        }
    }

    fun evaluateRoute() {
        val state = _uiState.value
        val height = state.height.toDoubleOrNull()
        val width = state.width.toDoubleOrNull()
        val weight = state.weight.toDoubleOrNull()
        val trainHours = state.trainHours.toDoubleOrNull()
        val berthStartHours = state.berthStartHours.toDoubleOrNull()
        val berthEndHours = state.berthEndHours.toDoubleOrNull()

        if (height == null || width == null || weight == null || trainHours == null ||
            height <= 0 || width <= 0 || weight <= 0 || trainHours <= 0 ||
            (state.useBerthWindow && (berthStartHours == null || berthEndHours == null || berthEndHours <= berthStartHours))
        ) {
            _uiState.update {
                it.copy(error = "Invalid entries detected. Cargo height and weight must be positive numeric values.")
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            try {
                val loadingWindow = if (state.useBerthWindow && berthStartHours != null && berthEndHours != null) {
                    LoadingWindowDto(
                        startTime = isoHoursFromNow(berthStartHours),
                        endTime = isoHoursFromNow(berthEndHours),
                    )
                } else null

                val result = repository.evaluateRoute(
                    height = height,
                    width = width,
                    weight = weight,
                    sourceCode = state.sourceCode,
                    destCode = state.destCode,
                    trainArrivalHours = trainHours,
                    stops = state.stops,
                    loadingWindow = loadingWindow,
                ).data

                // Fetch weather condition for coordinates midpoint and recalculate score breakdown
                val allCoords = result.segments.flatMap { it.coordinates }
                val weatherCondition = if (allCoords.isNotEmpty()) {
                    val midLat = allCoords.map { it[0] }.average()
                    val midLon = allCoords.map { it[1] }.average()
                    repository.fetchWeatherForRoute(midLat, midLon)
                } else {
                    null
                }

                val weatherScore = WeatherService.weatherToScore(weatherCondition)
                val updatedReliability = if (result.status == "HARD_BLOCKED") {
                    0
                } else {
                    val baseComp = result.reliabilityScore.toDouble() - (0.40 * 82.0) + (0.40 * weatherScore)
                    kotlin.math.ceil(baseComp).toInt().coerceIn(0, 100)
                }

                val finalResult = result.copy(
                    reliabilityScore = updatedReliability,
                    scoreBreakdown = result.scoreBreakdown?.copy(weather = weatherScore.toDouble())
                        ?: ScoreBreakdown(weather = weatherScore.toDouble(), port = 85.0, congestion = 72.0, historical = 90.0)
                )

                _uiState.update {
                    it.copy(
                        isLoading = false,
                        result = finalResult,
                        simulatedScore = null,
                        simAlerts = emptyList(),
                        selectedTab = DashboardTab.ROUTE_SELECTION,
                    )
                }
            } catch (e: IllegalArgumentException) {
                _uiState.update {
                    it.copy(isLoading = false, error = e.message)
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        error = e.message ?: "Route evaluation failed. Please try again.",
                    )
                }
            }
        }
    }

    fun simulateThreat() {
        val state = _uiState.value
        val baseScore = state.result?.reliabilityScore ?: 85
        viewModelScope.launch {
            _uiState.update { it.copy(simLoading = true) }
            try {
                val response = repository.simulateThreat(
                    baseScore = baseScore,
                    stormSeverity = state.stormSeverity.toDouble(),
                    solarKpIndex = state.solarKp.toInt(),
                    portCongestion = state.portCongestion.toDouble(),
                ).data
                _uiState.update {
                    it.copy(
                        simLoading = false,
                        simulatedScore = response.simulatedScore,
                        simAlerts = response.alerts,
                    )
                }
            } catch (_: Exception) {
                _uiState.update { it.copy(simLoading = false) }
            }
        }
    }

    fun calculateEstimatedTime() {
        val state = _uiState.value
        val baseHours = (state.result?.estimatedHours ?: 0.0).toFloat()
        // Add 0.5 hour per additional stop as heuristic
        val extraHours = state.stops.size * 0.5f
        val total = baseHours + extraHours
        _uiState.update { it.copy(estimatedTotalHours = total) }
    }

    fun onRouteConfirmed(
        route: com.clearpath.nexus.data.model.AlternateRoute,
        allRoutes: List<com.clearpath.nexus.data.model.AlternateRoute>
    ) {
        val state = _uiState.value
        _uiState.update {
            it.copy(
                result = RouteEvaluateResponse(
                    routeId = route.id,
                    status = route.status,
                    reliabilityScore = route.reliabilityScore,
                    estimatedHours = route.estimatedHours,
                    scoreBreakdown = route.scoreBreakdown?.copy(
                        weather = route.weatherScore.toDouble()
                    ) ?: ScoreBreakdown(
                        weather = route.weatherScore.toDouble(),
                        port = 85.0,
                        congestion = 72.0,
                        historical = 90.0,
                    ),
                    segments = route.segments,
                ),
                confirmedRouteLabel = route.label,
                confirmedRouteId = route.id,
                alternateRoutes = allRoutes,
                selectedTab = DashboardTab.MAP,
            )
        }
        // Update estimated total hours after confirming route
        calculateEstimatedTime()

        // Save route evaluation to Supabase
        viewModelScope.launch {
            try {
                val userId = SupabaseClient.client.auth.currentUserOrNull()?.id
                if (userId != null) {
                    val height = state.height.toDoubleOrNull() ?: 0.0
                    val width = state.width.toDoubleOrNull() ?: 0.0
                    val weight = state.weight.toDoubleOrNull() ?: 0.0

                    val row = RouteEvaluationRow(
                        userId = userId,
                        sourceCode = state.sourceCode,
                        destCode = state.destCode,
                        cargoHeight = height,
                        cargoWidth = width,
                        cargoWeight = weight,
                        selectedRouteLabel = route.label,
                        reliabilityScore = route.reliabilityScore,
                        weatherScore = route.weatherScore,
                        status = route.status,
                        estimatedHours = route.estimatedHours
                    )
                    repository.saveRouteEvaluation(row)
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun onBackFromRouteSelection() {
        _uiState.update { it.copy(selectedTab = DashboardTab.CONFIGURE) }
    }

    fun loadSavedProfiles(context: android.content.Context) {
        val sharedPrefs = context.getSharedPreferences("clearpath_prefs", android.content.Context.MODE_PRIVATE)
        val jsonStr = sharedPrefs.getString("load_profiles", null)
        val list = if (!jsonStr.isNullOrEmpty()) {
            try {
                kotlinx.serialization.json.Json.decodeFromString<List<LoadProfile>>(jsonStr)
            } catch (e: Exception) {
                emptyList()
            }
        } else {
            // Seed a default profile if none exists
            val defaultProfiles = listOf(
                LoadProfile(
                    id = "lp-std",
                    name = "Standard Container",
                    height = 4.5,
                    width = 3.2,
                    weight = 120.0,
                    compartments = 1,
                    compartmentPurpose = "General cargo",
                    notes = "Standard ISO dry van",
                    createdAt = "2026-06-13T00:00:00Z"
                )
            )
            try {
                val seedStr = kotlinx.serialization.json.Json.encodeToString(defaultProfiles)
                sharedPrefs.edit().putString("load_profiles", seedStr).apply()
            } catch (e: Exception) {}
            defaultProfiles
        }

        // Load saved inputs
        val height = sharedPrefs.getString("input_height", "4.8") ?: "4.8"
        val width = sharedPrefs.getString("input_width", "3.2") ?: "3.2"
        val weight = sharedPrefs.getString("input_weight", "120") ?: "120"
        val source = sharedPrefs.getString("input_source", "NGP") ?: "NGP"
        val dest = sharedPrefs.getString("input_dest", "JNPT") ?: "JNPT"
        val hours = sharedPrefs.getString("input_hours", "24") ?: "24"
        val profileId = sharedPrefs.getString("input_profile_id", null)
        val stopsJson = sharedPrefs.getString("input_stops", null)
        val stops = if (!stopsJson.isNullOrEmpty()) {
            try {
                kotlinx.serialization.json.Json.decodeFromString<List<String>>(stopsJson)
            } catch (e: Exception) {
                emptyList()
            }
        } else {
            emptyList()
        }

        _uiState.update {
            it.copy(
                loadProfiles = list,
                height = height,
                width = width,
                weight = weight,
                sourceCode = source,
                destCode = dest,
                trainHours = hours,
                selectedProfileId = profileId,
                stops = stops
            )
        }
    }

    fun saveCurrentInputs(
        context: android.content.Context,
        height: String,
        width: String,
        weight: String,
        source: String,
        dest: String,
        hours: String,
        stops: List<String>,
        profileId: String?
    ) {
        val sharedPrefs = context.getSharedPreferences("clearpath_prefs", android.content.Context.MODE_PRIVATE)
        try {
            val stopsJson = kotlinx.serialization.json.Json.encodeToString(stops)
            sharedPrefs.edit()
                .putString("input_height", height)
                .putString("input_width", width)
                .putString("input_weight", weight)
                .putString("input_source", source)
                .putString("input_dest", dest)
                .putString("input_hours", hours)
                .putString("input_stops", stopsJson)
                .putString("input_profile_id", profileId)
                .apply()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun saveProfilesList(context: android.content.Context, list: List<LoadProfile>) {
        val sharedPrefs = context.getSharedPreferences("clearpath_prefs", android.content.Context.MODE_PRIVATE)
        try {
            val jsonStr = kotlinx.serialization.json.Json.encodeToString(list)
            sharedPrefs.edit().putString("load_profiles", jsonStr).apply()
            _uiState.update { it.copy(loadProfiles = list) }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun saveLoadProfile(
        context: android.content.Context,
        name: String,
        height: Double,
        width: Double,
        weight: Double,
        compartments: Int,
        purpose: String,
        notes: String
    ) {
        val current = _uiState.value.loadProfiles.toMutableList()
        val newProfile = LoadProfile(
            id = "lp-${System.currentTimeMillis()}",
            name = name,
            height = height,
            width = width,
            weight = weight,
            compartments = compartments,
            compartmentPurpose = purpose,
            notes = notes,
            createdAt = "2026-06-13T00:00:00Z"
        )
        current.add(newProfile)
        saveProfilesList(context, current)
        selectLoadProfile(newProfile.id)
    }

    fun deleteLoadProfile(context: android.content.Context, id: String) {
        val current = _uiState.value.loadProfiles.filter { it.id != id }
        saveProfilesList(context, current)
        if (_uiState.value.selectedProfileId == id) {
            _uiState.update { it.copy(selectedProfileId = null) }
        }
    }

    fun selectLoadProfile(id: String) {
        val profile = _uiState.value.loadProfiles.find { it.id == id }
        if (profile != null) {
            _uiState.update {
                it.copy(
                    selectedProfileId = id,
                    height = profile.height.toString(),
                    width = profile.width.toString(),
                    weight = profile.weight.toString()
                )
            }
        } else {
            _uiState.update { it.copy(selectedProfileId = null) }
        }
    }
    private fun isoHoursFromNow(hours: Double): String {
        val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        calendar.timeInMillis += (hours * 60.0 * 60.0 * 1000.0).toLong()
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        format.timeZone = TimeZone.getTimeZone("UTC")
        return format.format(calendar.time)
    }

}

