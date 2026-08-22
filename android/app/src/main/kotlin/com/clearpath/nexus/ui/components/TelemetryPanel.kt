package com.clearpath.nexus.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.clearpath.nexus.data.model.LoadProfile
import com.clearpath.nexus.data.model.RouteEvaluateResponse
import com.clearpath.nexus.ui.theme.AccentSafetyBlue
import com.clearpath.nexus.ui.theme.PanelBorder
import com.clearpath.nexus.ui.theme.PanelDark
import com.clearpath.nexus.ui.theme.PrimaryCommandBlue
import com.clearpath.nexus.ui.theme.SolarRiskAmber
import com.clearpath.nexus.ui.theme.StatusApprovedGreen
import com.clearpath.nexus.ui.theme.StatusBlockedRed
import com.clearpath.nexus.ui.theme.TextLight
import com.clearpath.nexus.ui.theme.TextMuted

@Composable
fun TelemetryPanel(
    result: RouteEvaluateResponse?,
    activeProfile: LoadProfile?,
    stormSeverity: Float,
    solarKp: Float,
    portCongestion: Float,
    simLoading: Boolean,
    simulatedScore: Int?,
    simAlerts: List<String>,
    onStormChange: (Float) -> Unit,
    onSolarChange: (Float) -> Unit,
    onPortChange: (Float) -> Unit,
    onSimulate: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scrollState = rememberScrollState()
    val statusColor = when (result?.status) {
        "HARD_BLOCKED" -> StatusBlockedRed
        "APPROVED" -> StatusApprovedGreen
        else -> TextMuted
    }

    Column(
        modifier = modifier
            .verticalScroll(scrollState)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "TELEMETRY BOARD",
            color = TextLight,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp,
        )

        // ── Reliability Index Block ──────────────────────────────────────────
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, PanelBorder)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = "ROUTE RELIABILITY INDEX",
                color = TextMuted,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
            )
            Text(
                text = simulatedScore?.toString() ?: (result?.reliabilityScore?.toString() ?: "—"),
                color = if (simulatedScore != null) SolarRiskAmber else statusColor,
                fontSize = 48.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
            )
            result?.status?.let {
                Text(
                    text = it,
                    color = statusColor,
                    fontSize = 14.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Medium,
                )
            }
            result?.estimatedHours?.let {
                Text(
                    text = "Est. transit: ${it}h",
                    color = TextMuted,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                )
            }
        }

        // ── Score Breakdown ──────────────────────────────────────────────────
        result?.scoreBreakdown?.let { breakdown ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, PanelBorder)
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                ScoreItem("Weather", breakdown.weather)
                ScoreItem("Port Sync", breakdown.port)
                ScoreItem("Congestion", breakdown.congestion)
                ScoreItem("Historical", breakdown.historical)
            }
        }

        result?.provenanceSummary?.let { sourceLine ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, AccentSafetyBlue.copy(alpha = 0.45f))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text("NEXUS SOURCELINE", color = AccentSafetyBlue, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(
                    "Traceability: ${sourceLine.tracedInputs} / ${sourceLine.totalInputs} decision inputs (${sourceLine.coveragePct}%)",
                    color = TextLight,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                )
                sourceLine.warnings.firstOrNull()?.let { warning ->
                    Text(warning, color = SolarRiskAmber, fontSize = 10.sp)
                }
            }
        }

        // ── Active Cargo Load Profile ────────────────────────────────────────
        if (activeProfile != null) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(
                        Brush.linearGradient(
                            listOf(PrimaryCommandBlue.copy(alpha = 0.3f), PanelDark.copy(alpha = 0.5f))
                        )
                    )
                    .border(1.dp, AccentSafetyBlue.copy(alpha = 0.4f), RoundedCornerShape(12.dp))
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Default.Inventory2,
                        contentDescription = null,
                        tint = AccentSafetyBlue,
                        modifier = Modifier.size(14.dp)
                    )
                    Text(
                        text = "ACTIVE CARGO PROFILE",
                        color = AccentSafetyBlue,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.5.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
                Text(
                    text = activeProfile.name,
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                // Dimension metrics row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CargoMetricCell("HEIGHT", "${activeProfile.height} m", AccentSafetyBlue, Modifier.weight(1f))
                    CargoMetricCell("WIDTH", "${activeProfile.width} m", SolarRiskAmber, Modifier.weight(1f))
                    CargoMetricCell("WEIGHT", "${activeProfile.weight} T", StatusApprovedGreen, Modifier.weight(1f))
                }

                // Derived telemetry specific to this profile
                val loadFactor = (activeProfile.weight / 150.0).coerceIn(0.0, 1.0)
                val volumeM3 = activeProfile.height * activeProfile.width * 12.0 // assume 12m length
                val axleLoad = activeProfile.weight / (activeProfile.compartments.coerceAtLeast(1) * 2.0)
                val clearanceMargin = if (activeProfile.height < 4.5 && activeProfile.width < 3.2) "SAFE" else "CHECK"
                val clearanceColor = if (clearanceMargin == "SAFE") StatusApprovedGreen else SolarRiskAmber

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CargoMetricCell(
                        label = "LOAD FACTOR",
                        value = "${"%.0f".format(loadFactor * 100)}%",
                        accent = if (loadFactor > 0.85) StatusBlockedRed else if (loadFactor > 0.65) SolarRiskAmber else StatusApprovedGreen,
                        modifier = Modifier.weight(1f)
                    )
                    CargoMetricCell("VOL. EST.", "${"%.1f".format(volumeM3)} m³", TextLight, Modifier.weight(1f))
                    CargoMetricCell("AXLE LOAD", "${"%.1f".format(axleLoad)} T", TextLight, Modifier.weight(1f))
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CargoMetricCell("COMPARTMENTS", "${activeProfile.compartments}", AccentSafetyBlue.copy(alpha = 0.8f), Modifier.weight(1f))
                    Box(
                        modifier = Modifier
                            .weight(2f)
                            .background(clearanceColor.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                            .border(1.dp, clearanceColor.copy(alpha = 0.4f), RoundedCornerShape(8.dp))
                            .padding(horizontal = 10.dp, vertical = 8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("CLEARANCE", color = TextMuted, fontSize = 9.sp, fontFamily = FontFamily.Monospace, letterSpacing = 1.sp)
                            Spacer(Modifier.height(4.dp))
                            Text(clearanceMargin, color = clearanceColor, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                    }
                }

                if (activeProfile.compartmentPurpose.isNotBlank()) {
                    Text(
                        text = "Purpose: ${activeProfile.compartmentPurpose}",
                        color = TextMuted,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(PanelDark.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
                            .padding(horizontal = 10.dp, vertical = 6.dp)
                    )
                }
                if (activeProfile.notes.isNotBlank()) {
                    Text(
                        text = "📋  ${activeProfile.notes}",
                        color = TextMuted.copy(alpha = 0.7f),
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        } else {
            // No profile selected placeholder
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, PanelBorder.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(Icons.Default.Inventory2, contentDescription = null, tint = TextMuted, modifier = Modifier.size(24.dp))
                Text("No cargo profile selected", color = TextMuted, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                Text("Select a profile in the Loads tab to see cargo telemetry", color = TextMuted.copy(alpha = 0.6f), fontSize = 10.sp, fontFamily = FontFamily.Monospace)
            }
        }

        // ── Environmental Alerts ──────────────────────────────────────────────
        if (!result?.environmentalAlerts.isNullOrEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, StatusBlockedRed.copy(alpha = 0.5f))
                    .padding(12.dp),
            ) {
                Text(
                    text = "ENVIRONMENTAL ALERTS",
                    color = StatusBlockedRed,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                )
                result!!.environmentalAlerts.forEach { alert ->
                    Text(
                        text = "⚠ $alert",
                        color = StatusBlockedRed.copy(alpha = 0.8f),
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
        }

        ThreatSimulator(
            stormSeverity = stormSeverity,
            solarKp = solarKp,
            portCongestion = portCongestion,
            simLoading = simLoading,
            simulatedScore = simulatedScore,
            simAlerts = simAlerts,
            onStormChange = onStormChange,
            onSolarChange = onSolarChange,
            onPortChange = onPortChange,
            onSimulate = onSimulate,
        )

        if (result?.status == "APPROVED") {
            Button(
                onClick = { },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = AccentSafetyBlue),
            ) {
                Text("Finalize and Dispatch Route")
            }
        }
    }
}

@Composable
private fun ScoreItem(label: String, value: Double) {
    Column {
        Text(label, color = TextMuted, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Text(
            text = value.toInt().toString(),
            color = TextLight,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
        )
    }
}

@Composable
private fun CargoMetricCell(label: String, value: String, accent: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(PanelDark.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
            .border(1.dp, accent.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
            .padding(horizontal = 6.dp, vertical = 7.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = label,
            color = TextMuted,
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 0.5.sp,
            maxLines = 1,
            overflow = TextOverflow.Clip
        )
        Spacer(Modifier.height(3.dp))
        Text(
            text = value,
            color = accent,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}
