package com.clearpath.nexus.ui.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.clearpath.nexus.ui.theme.*
import com.clearpath.nexus.R
import androidx.compose.ui.res.painterResource

fun loadBitmapFromUri(context: Context, uriString: String): Bitmap? {
    return try {
        val uri = Uri.parse(uriString)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val source = ImageDecoder.createSource(context.contentResolver, uri)
            ImageDecoder.decodeBitmap(source)
        } else {
            @Suppress("DEPRECATION")
            MediaStore.Images.Media.getBitmap(context.contentResolver, uri)
        }
    } catch (e: Exception) {
        e.printStackTrace()
        null
    }
}

@Composable
fun UserPanel(
    onSignOut: () -> Unit,
    userEmail: String? = null,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val sharedPrefs = remember { context.getSharedPreferences("clearpath_prefs", Context.MODE_PRIVATE) }
    var profileUriString by remember { mutableStateOf(sharedPrefs.getString("profile_uri", null)) }

    val profileBitmap = remember(profileUriString) {
        if (!profileUriString.isNullOrEmpty()) {
            loadBitmapFromUri(context, profileUriString!!)
        } else {
            null
        }
    }

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            profileUriString = uri.toString()
            sharedPrefs.edit().putString("profile_uri", uri.toString()).apply()
        }
    }

    val email = userEmail ?: "anonymous@clearpath.net"
    val displayName = "Command Officer"

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(TelemetryCanvasDark)
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        // App name & version header in User tab
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(bottom = 8.dp)
        ) {
            Image(
                painter = painterResource(id = R.drawable.app_logo),
                contentDescription = "ClearPath Nexus Logo",
                modifier = Modifier
                    .size(64.dp)
                    .clip(CircleShape)
                    .border(2.dp, AccentSafetyBlue, CircleShape)
            )
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "CLEARPATH NEXUS",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
                letterSpacing = 2.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "AI-Powered Railway Intelligence Command Center",
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                color = TextLight,
                textAlign = TextAlign.Center
            )
        }

        // Profile Picture & Edit Button
        Box(
            modifier = Modifier
                .size(120.dp)
                .clickable { launcher.launch("image/*") },
            contentAlignment = Alignment.Center
        ) {
            if (profileBitmap != null) {
                Image(
                    bitmap = profileBitmap.asImageBitmap(),
                    contentDescription = "Profile Picture",
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(CircleShape)
                        .border(3.dp, AccentSafetyBlue, CircleShape),
                    contentScale = ContentScale.Crop
                )
            } else {
                Icon(
                    imageVector = Icons.Default.AccountCircle,
                    contentDescription = "Profile Placeholder",
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(CircleShape)
                        .background(PanelDark)
                        .border(3.dp, PanelBorder, CircleShape),
                    tint = TextMuted
                )
            }

            // Small camera icon overlay at bottom right
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(AccentSafetyBlue)
                    .border(2.dp, PanelDark, CircleShape)
                    .align(Alignment.BottomEnd),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.PhotoCamera,
                    contentDescription = "Change Profile Photo",
                    modifier = Modifier.size(16.dp),
                    tint = Color.White
                )
            }
        }

        // User Details Card
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, PanelBorder, RoundedCornerShape(12.dp))
                .background(PanelDark, RoundedCornerShape(12.dp))
                .padding(20.dp)
        ) {
            Text(
                text = displayName,
                fontWeight = FontWeight.Bold,
                color = Color.White,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = email,
                color = TextMuted,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(16.dp))

            // Sync Status & Version
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .background(StatusApprovedGreen, RoundedCornerShape(6.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.CloudDone,
                        contentDescription = "Synced Status",
                        modifier = Modifier.size(14.dp),
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "CLOUD SYNCED",
                        color = Color.White,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Text(
                    text = "v1.2",
                    color = TextLight,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier
                        .border(1.dp, TextLight.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
                        .background(TextLight.copy(alpha = 0.1f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                )
            }
        }

        // About the App Documentation Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = PanelDark),
            border = BorderStroke(1.dp, PanelBorder)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Info, contentDescription = null, tint = AccentSafetyBlue, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("ABOUT THE PLATFORM", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp, fontFamily = FontFamily.Monospace)
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    text = "ClearPath Nexus is a state-of-the-art railway intelligence command interface. Powered by advanced predictive routing heuristics and real-time environmental telemetry, the application evaluates segment hazards, weather profiles, solar geomagnetic storms, and destination constraints to provide optimal routing safety indices.",
                    color = TextMuted,
                    fontSize = 12.sp,
                    lineHeight = 18.sp
                )
            }
        }

        // Necessary Documentation & Terms Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = PanelDark),
            border = BorderStroke(1.dp, PanelBorder)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = "TERMS & OPERATIONS RULES",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    text = "1. Operational clearance models must be validated prior to launching command units.\n\n2. Real-time telemetry simulation values do not supersede local authority signaling protocols.\n\n3. Routing data is sent to the configured ClearPath backend over the authenticated API.",
                    color = TextMuted,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }

        // Sign Out Button
        Button(
            onClick = onSignOut,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            colors = ButtonDefaults.buttonColors(containerColor = StatusBlockedRed),
            shape = RoundedCornerShape(10.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Logout,
                contentDescription = "Sign Out",
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "DISCONNECT SESSION",
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}
