package com.clearpath.nexus.ui.screens

import android.content.Context
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.BackHandler
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.clearpath.nexus.ui.components.ConfigPanel
import com.clearpath.nexus.ui.components.LoadProfilesPanel
import com.clearpath.nexus.ui.components.RouteMapView
import com.clearpath.nexus.ui.components.TelemetryPanel
import com.clearpath.nexus.ui.components.UserPanel
import com.clearpath.nexus.ui.components.loadBitmapFromUri
import com.clearpath.nexus.ui.theme.AccentSafetyBlue
import com.clearpath.nexus.ui.theme.PanelDark
import com.clearpath.nexus.ui.theme.PrimaryCommandBlue
import com.clearpath.nexus.ui.theme.SolarRiskAmber
import com.clearpath.nexus.ui.theme.StatusApprovedGreen
import com.clearpath.nexus.ui.theme.TelemetryCanvasDark
import com.clearpath.nexus.ui.theme.TextLight
import com.clearpath.nexus.viewmodel.DashboardTab
import com.clearpath.nexus.viewmodel.DashboardViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CommandDashboardScreen(
    viewModel: DashboardViewModel = viewModel(),
    onSignOut: () -> Unit,
) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var showAddDestinationDialog by remember { mutableStateOf(false) }

    val sharedPrefs = remember { context.getSharedPreferences("clearpath_prefs", Context.MODE_PRIVATE) }
    var profileUriString by remember { mutableStateOf(sharedPrefs.getString("profile_uri", null)) }

    val listener = remember {
        android.content.SharedPreferences.OnSharedPreferenceChangeListener { prefs, key ->
            if (key == "profile_uri") {
                profileUriString = prefs.getString("profile_uri", null)
            }
        }
    }
    DisposableEffect(Unit) {
        sharedPrefs.registerOnSharedPreferenceChangeListener(listener)
        onDispose {
            sharedPrefs.unregisterOnSharedPreferenceChangeListener(listener)
        }
    }

    LaunchedEffect(Unit) {
        viewModel.loadSavedProfiles(context)
    }

    LaunchedEffect(
        state.height,
        state.width,
        state.weight,
        state.sourceCode,
        state.destCode,
        state.trainHours,
        state.stops,
        state.selectedProfileId
    ) {
        viewModel.saveCurrentInputs(
            context = context,
            height = state.height,
            width = state.width,
            weight = state.weight,
            source = state.sourceCode,
            dest = state.destCode,
            hours = state.trainHours,
            stops = state.stops,
            profileId = state.selectedProfileId
        )
    }

    val navProfileBitmap = remember(profileUriString) {
        if (!profileUriString.isNullOrEmpty()) {
            loadBitmapFromUri(context, profileUriString!!)
        } else {
            null
        }
    }

    if (state.selectedTab != DashboardTab.CONFIGURE && state.selectedTab != DashboardTab.ROUTE_SELECTION) {
        BackHandler {
            viewModel.onTabSelected(DashboardTab.CONFIGURE)
        }
    }

    // ── Route Selection is a full-screen takeover ────────────────────
    if (state.selectedTab == DashboardTab.ROUTE_SELECTION) {
        val h = state.height.toDoubleOrNull() ?: 4.8
        val w = state.width.toDoubleOrNull() ?: 3.2
        val wt = state.weight.toDoubleOrNull() ?: 120.0
        val hrs = state.trainHours.toDoubleOrNull() ?: 24.0

        RouteSelectionScreen(
            height = h,
            width = w,
            weight = wt,
            sourceCode = state.sourceCode,
            destCode = state.destCode,
            trainHours = hrs,
            stops = state.stops,
            onRouteConfirmed = { route, allRoutes -> viewModel.onRouteConfirmed(route, allRoutes) },
            onBack = { viewModel.onBackFromRouteSelection() },
        )
        return
    }

    // ── Normal Dashboard ─────────────────────────────────────────────
    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = PanelDark,
                tonalElevation = 0.dp
            ) {
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.CONFIGURE,
                    onClick = { viewModel.onTabSelected(DashboardTab.CONFIGURE) },
                    icon = { Icon(Icons.Default.Settings, contentDescription = "Configure", modifier = Modifier.size(20.dp)) },
                    label = { Text("Configure", fontSize = 9.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.MAP,
                    onClick = { viewModel.onTabSelected(DashboardTab.MAP) },
                    icon = { Icon(Icons.Default.Map, contentDescription = "Map", modifier = Modifier.size(20.dp)) },
                    label = { Text("Map", fontSize = 9.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.TELEMETRY,
                    onClick = { viewModel.onTabSelected(DashboardTab.TELEMETRY) },
                    icon = { Icon(Icons.Default.Speed, contentDescription = "Telemetry", modifier = Modifier.size(20.dp)) },
                    label = { Text("Telemetry", fontSize = 9.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.SCHEDULE,
                    onClick = { viewModel.onTabSelected(DashboardTab.SCHEDULE) },
                    icon = { Icon(Icons.Default.Schedule, contentDescription = "Schedule", modifier = Modifier.size(20.dp)) },
                    label = { Text("Schedule", fontSize = 8.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.HISTORY,
                    onClick = { viewModel.onTabSelected(DashboardTab.HISTORY) },
                    icon = { Icon(Icons.Default.History, contentDescription = "History", modifier = Modifier.size(20.dp)) },
                    label = { Text("Log", fontSize = 8.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.LOADS,
                    onClick = { viewModel.onTabSelected(DashboardTab.LOADS) },
                    icon = { Icon(Icons.Default.Inventory2, contentDescription = "Loads", modifier = Modifier.size(20.dp)) },
                    label = { Text("Loads", fontSize = 9.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = state.selectedTab == DashboardTab.USER,
                    onClick = { viewModel.onTabSelected(DashboardTab.USER) },
                    icon = {
                        if (navProfileBitmap != null) {
                            Image(
                                bitmap = navProfileBitmap.asImageBitmap(),
                                contentDescription = "User",
                                modifier = Modifier.size(20.dp).clip(CircleShape),
                                contentScale = ContentScale.Crop
                            )
                        } else {
                            Icon(Icons.Default.AccountCircle, contentDescription = "User", modifier = Modifier.size(20.dp))
                        }
                    },
                    label = { Text("User", fontSize = 9.sp, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Clip) },
                    colors = navColors(),
                )
            }
        },
        containerColor = PrimaryCommandBlue,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(
                    when (state.selectedTab) {
                        DashboardTab.MAP -> TelemetryCanvasDark
                        else -> PanelDark
                    },
                ),
        ) {
            when (state.selectedTab) {
                DashboardTab.CONFIGURE -> ConfigPanel(
                    height = state.height,
                    width = state.width,
                    weight = state.weight,
                    sourceCode = state.sourceCode,
                    destCode = state.destCode,
                    trainHours = state.trainHours,
                    useBerthWindow = state.useBerthWindow,
                    berthStartHours = state.berthStartHours,
                    berthEndHours = state.berthEndHours,
                    stations = state.stations,
                    stops = state.stops,
                    isLoading = state.isLoading,
                    error = state.error,
                    onHeightChange = viewModel::onHeightChange,
                    onWidthChange = viewModel::onWidthChange,
                    onWeightChange = viewModel::onWeightChange,
                    onSourceChange = viewModel::onSourceChange,
                    onDestChange = viewModel::onDestChange,
                    onTrainHoursChange = viewModel::onTrainHoursChange,
                    onUseBerthWindowChange = viewModel::onUseBerthWindowChange,
                    onBerthStartHoursChange = viewModel::onBerthStartHoursChange,
                    onBerthEndHoursChange = viewModel::onBerthEndHoursChange,
                    onStopsChange = viewModel::onStopsChange,
                    onAddStopClick = { showAddDestinationDialog = true },
                    onEvaluate = viewModel::evaluateRoute,
                    modifier = Modifier.fillMaxSize(),
                )

                DashboardTab.MAP -> RouteMapView(
                    segments = state.result?.segments ?: emptyList(),
                    alternateRoutes = state.alternateRoutes,
                    selectedRouteId = state.confirmedRouteId,
                    stations = state.stations,
                    environmentalZones = state.environmentalZones,
                    estimatedTotalHours = state.estimatedTotalHours,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(8.dp),
                    onConfirm = {
                        val label = state.confirmedRouteLabel ?: "Default"
                        android.widget.Toast.makeText(context, "Route confirmed: $label", android.widget.Toast.LENGTH_SHORT).show()
                    },
                )

                DashboardTab.TELEMETRY -> TelemetryPanel(
                    result = state.result,
                    activeProfile = state.loadProfiles.find { it.id == state.selectedProfileId },
                    stormSeverity = state.stormSeverity,
                    solarKp = state.solarKp,
                    portCongestion = state.portCongestion,
                    simLoading = state.simLoading,
                    simulatedScore = state.simulatedScore,
                    simAlerts = state.simAlerts,
                    onStormChange = viewModel::onStormChange,
                    onSolarChange = viewModel::onSolarChange,
                    onPortChange = viewModel::onPortChange,
                    onSimulate = viewModel::simulateThreat,
                    modifier = Modifier.fillMaxSize(),
                )

                DashboardTab.SCHEDULE -> ScheduleScreen(modifier = Modifier.fillMaxSize())

                DashboardTab.HISTORY -> DispatchHistoryScreen(modifier = Modifier.fillMaxSize())

                DashboardTab.LOADS -> LoadProfilesPanel(
                    loadProfiles = state.loadProfiles,
                    selectedProfileId = state.selectedProfileId,
                    onProfileSelect = viewModel::selectLoadProfile,
                    onProfileSave = { name, h, w, wt, comp, purp, notes ->
                        viewModel.saveLoadProfile(context, name, h, w, wt, comp, purp, notes)
                    },
                    onProfileDelete = { id -> viewModel.deleteLoadProfile(context, id) },
                    modifier = Modifier.fillMaxSize(),
                )

                DashboardTab.USER -> UserPanel(
                    onSignOut = onSignOut,
                    modifier = Modifier.fillMaxSize(),
                )

                // ROUTE_SELECTION handled above as full-screen takeover
                else -> { }
            }
        }
    }

    if (showAddDestinationDialog) {
        val availableStations = state.stations.filter { station ->
            station.code != state.sourceCode &&
            station.code != state.destCode &&
            station.code !in state.stops
        }
        AlertDialog(
            onDismissRequest = { showAddDestinationDialog = false },
            title = {
                Text(
                    text = "Add Destination Stop",
                    fontWeight = FontWeight.Bold,
                    color = androidx.compose.ui.graphics.Color.White
                )
            },
            text = {
                if (availableStations.isEmpty()) {
                    Text(
                        text = "No additional stations available.",
                        color = TextLight,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 12.sp
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier.heightIn(max = 300.dp)
                    ) {
                        items(availableStations) { station ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        val newStops = state.stops + station.code
                                        viewModel.onStopsChange(newStops)
                                        viewModel.calculateEstimatedTime()
                                        showAddDestinationDialog = false
                                    }
                                    .padding(vertical = 12.dp, horizontal = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = station.name,
                                        fontWeight = FontWeight.SemiBold,
                                        color = androidx.compose.ui.graphics.Color.White,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "Code: ${station.code}",
                                        color = TextLight.copy(alpha = 0.7f),
                                        fontSize = 11.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showAddDestinationDialog = false }) {
                    Text("Cancel", color = AccentSafetyBlue)
                }
            },
            containerColor = PanelDark,
            textContentColor = androidx.compose.ui.graphics.Color.White
        )
    }
}

@Composable
private fun navColors() = NavigationBarItemDefaults.colors(
    selectedIconColor = AccentSafetyBlue,
    selectedTextColor = AccentSafetyBlue,
    indicatorColor = AccentSafetyBlue.copy(alpha = 0.2f),
    unselectedIconColor = TextLight.copy(alpha = 0.6f),
    unselectedTextColor = TextLight.copy(alpha = 0.6f),
)
