package com.clearpath.nexus.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.Checkbox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.clearpath.nexus.data.model.Station

import com.clearpath.nexus.ui.theme.AccentSafetyBlue
import com.clearpath.nexus.ui.theme.PanelBorder
import com.clearpath.nexus.ui.theme.PanelDark
import com.clearpath.nexus.ui.theme.StatusBlockedRed
import com.clearpath.nexus.ui.theme.TextLight
import com.clearpath.nexus.ui.theme.TextMuted

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConfigPanel(
    height: String,
    width: String,
    weight: String,
    sourceCode: String,
    destCode: String,
    trainHours: String,
    useBerthWindow: Boolean,
    berthStartHours: String,
    berthEndHours: String,
    stations: List<Station>,
    stops: List<String>,
    isLoading: Boolean,
    error: String?,
    onHeightChange: (String) -> Unit,
    onWidthChange: (String) -> Unit,
    onWeightChange: (String) -> Unit,
    onSourceChange: (String) -> Unit,
    onDestChange: (String) -> Unit,
    onTrainHoursChange: (String) -> Unit,
    onUseBerthWindowChange: (Boolean) -> Unit,
    onBerthStartHoursChange: (String) -> Unit,
    onBerthEndHoursChange: (String) -> Unit,
    onStopsChange: (List<String>) -> Unit,
    onAddStopClick: () -> Unit,
    onEvaluate: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scrollState = rememberScrollState()
    val stationCodes = stations.map { it.code }.ifEmpty {
        listOf("NGP", "BSL", "MMR", "KYN", "JNPT", "PUNE")
    }

    Column(
        modifier = modifier
            .verticalScroll(scrollState)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "CONFIGURATION INPUT",
            color = TextLight,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp,
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DimensionField("Height (m)", height, onHeightChange, Modifier.weight(1f))
            DimensionField("Width (m)", width, onWidthChange, Modifier.weight(1f))
            DimensionField("Weight (T)", weight, onWeightChange, Modifier.weight(1f))
        }

        StationDropdown("Source Station", sourceCode, stationCodes, stations, onSourceChange)
        StationDropdown("Destination", destCode, stationCodes, stations, onDestChange)

        // --- Waypoints / Stops section ---
        if (stops.isNotEmpty()) {
            Text(
                text = "SELECTED WAYPOINTS",
                color = TextLight,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
            stops.forEach { stopCode ->
                val stationName = stations.find { it.code == stopCode }?.name ?: stopCode
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(PanelDark, RoundedCornerShape(6.dp))
                        .border(1.dp, PanelBorder, RoundedCornerShape(6.dp))
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
                ) {
                    Text(
                        text = "$stopCode — $stationName",
                        color = Color.White,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                    )
                    Text(
                        text = "Remove",
                        color = StatusBlockedRed,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.clickable {
                            onStopsChange(stops.filter { it != stopCode })
                        }
                    )
                }
            }
        }

        Button(
            onClick = onAddStopClick,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = PanelDark),
            border = androidx.compose.foundation.BorderStroke(1.dp, PanelBorder)
        ) {
            Text("+ Add Stop / Destination", color = AccentSafetyBlue, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
        }

        OutlinedTextField(
            value = trainHours,
            onValueChange = onTrainHoursChange,
            label = { Text("Train Arrival (hours from now)", fontFamily = FontFamily.Monospace, fontSize = 12.sp) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            colors = fieldColors(),
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            Checkbox(checked = useBerthWindow, onCheckedChange = onUseBerthWindowChange)
            Text("Use operator berth window", color = TextLight, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
        }

        if (useBerthWindow) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = berthStartHours,
                    onValueChange = onBerthStartHoursChange,
                    label = { Text("Berth starts in h", fontSize = 10.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    colors = fieldColors(),
                )
                OutlinedTextField(
                    value = berthEndHours,
                    onValueChange = onBerthEndHoursChange,
                    label = { Text("Berth ends in h", fontSize = 10.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    colors = fieldColors(),
                )
            }
            Text(
                "Operator/manifest window is sent to FastAPI; no fake live berth schedule.",
                color = TextMuted,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
            )
        }

        Button(
            onClick = onEvaluate,
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = AccentSafetyBlue),
        ) {
            Text(if (isLoading) "Evaluating Corridor…" else "Evaluate Corridor")
        }

        error?.let {
            Text(
                text = it,
                color = StatusBlockedRed,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
            )
        }
    }

}

@Composable
private fun DimensionField(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label, fontFamily = FontFamily.Monospace, fontSize = 11.sp) },
        modifier = modifier,
        singleLine = true,
        colors = fieldColors(),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StationDropdown(
    label: String,
    selected: String,
    codes: List<String>,
    stations: List<Station>,
    onSelected: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
    ) {
        OutlinedTextField(
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text(label, fontFamily = FontFamily.Monospace, fontSize = 12.sp) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth(),
            colors = fieldColors(),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            codes.forEach { code ->
                val station = stations.find { it.code == code }
                val display = station?.let { "${it.code} — ${it.name}" } ?: code
                DropdownMenuItem(
                    text = { Text(display, fontFamily = FontFamily.Monospace) },
                    onClick = {
                        onSelected(code)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = AccentSafetyBlue,
    unfocusedBorderColor = PanelBorder,
    focusedContainerColor = PanelDark,
    unfocusedContainerColor = PanelDark,
    focusedTextColor = androidx.compose.ui.graphics.Color.White,
    unfocusedTextColor = androidx.compose.ui.graphics.Color.White,
    focusedLabelColor = TextMuted,
    unfocusedLabelColor = TextMuted,
)
