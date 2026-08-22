package com.clearpath.nexus.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.clearpath.nexus.data.api.ApiClient
import com.clearpath.nexus.data.api.RouteHistoryDto
import com.clearpath.nexus.ui.theme.AccentSafetyBlue
import com.clearpath.nexus.ui.theme.PanelBorder
import com.clearpath.nexus.ui.theme.PanelDark
import com.clearpath.nexus.ui.theme.StatusApprovedGreen
import com.clearpath.nexus.ui.theme.StatusBlockedRed
import com.clearpath.nexus.ui.theme.TextLight
import com.clearpath.nexus.ui.theme.TextMuted
import kotlinx.coroutines.launch

@Composable
fun DispatchHistoryScreen(modifier: Modifier = Modifier) {
    var routes by remember { mutableStateOf<List<RouteHistoryDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            loading = true
            error = null
            try {
                routes = ApiClient.getRouteHistory()
            } catch (e: Exception) {
                error = e.message ?: "Could not load dispatch log"
            } finally {
                loading = false
            }
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Column(modifier = modifier.fillMaxSize().background(PanelDark).padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("ROUTE / DISPATCH LOG", color = TextLight, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Text("Current Supabase user only", color = TextMuted, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
            }
            Button(onClick = { refresh() }, colors = ButtonDefaults.buttonColors(containerColor = AccentSafetyBlue)) { Text("Refresh", fontSize = 11.sp) }
        }
        if (loading) Text("Loading route history…", color = TextMuted, fontFamily = FontFamily.Monospace)
        error?.let { Text(it, color = StatusBlockedRed, fontSize = 11.sp, fontFamily = FontFamily.Monospace) }
        if (!loading && routes.isEmpty()) Text("No evaluations yet.", color = TextMuted, fontFamily = FontFamily.Monospace)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(routes, key = { it.id }) { route ->
                Column(
                    modifier = Modifier.fillMaxWidth().background(Color(0xFF111827), RoundedCornerShape(10.dp)).border(1.dp, PanelBorder, RoundedCornerShape(10.dp)).padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(5.dp),
                ) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${route.sourceStationCode} → ${route.destStationCode}", color = AccentSafetyBlue, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                        Text(route.dispatchStatus, color = if (route.dispatchStatus == "DISPATCHED") StatusApprovedGreen else TextMuted, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    }
                    Text("Clearance: ${route.status} · Reliability: ${route.reliabilityScore}%", color = TextLight, fontSize = 11.sp)
                    Text("Cargo ${route.cargoHeightRequested}×${route.cargoWidthRequested}m / ${route.cargoWeightRequested}T", color = TextMuted, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Text(route.createdAt.replace('T', ' '), color = TextMuted, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                    Button(
                        onClick = {
                            scope.launch {
                                try {
                                    val dispatched = ApiClient.dispatchRoute(route.id)
                                    routes = routes.map { if (it.id == route.id) it.copy(dispatchStatus = dispatched.dispatchStatus, dispatchedAt = dispatched.dispatchedAt) else it }
                                } catch (e: Exception) {
                                    error = e.message ?: "Dispatch failed"
                                }
                            }
                        },
                        enabled = route.status == "APPROVED" && route.dispatchStatus != "DISPATCHED",
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = StatusApprovedGreen),
                    ) {
                        Text(if (route.dispatchStatus == "DISPATCHED") "DISPATCHED" else "FINALIZE & DISPATCH", fontSize = 10.sp)
                    }
                }
            }
        }
    }
}
