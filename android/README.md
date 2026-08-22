# ClearPath Nexus Android client

The Kotlin/Jetpack Compose client uses Supabase for authentication and sends the resulting bearer token to the FastAPI `/api/v1` operational backend. Backend authorization remains authoritative.

## Requirements

- JDK 17
- Android Studio and Android SDK 35
- A reachable FastAPI deployment
- Your public Supabase URL and anon key

Do not place a Supabase service-role key in this app.

## Configuration

Pass local Gradle properties or set them in the user-level Gradle properties file:

```properties
backendBaseUrl=http://10.0.2.2:8000/api/v1
supabaseUrl=https://your-project.supabase.co
supabaseAnonKey=your-public-anon-key
```

The committed defaults are placeholders. A physical device needs a backend address reachable from the device. Production releases require HTTPS, `releaseBackendBaseUrl`, and an external signing configuration.

## Verification

```powershell
.\gradlew.bat testDebugUnitTest assembleDebug
```

## Data-source behavior

Normal route decisions come from the FastAPI backend. If the offline engine is used, the repository sets `computedOffline` and the UI must display `OFFLINE_COMPUTED`; it must not be represented as live backend intelligence.

Android v6 parses the compact SourceLine traceability summary. Full evidence inspection and ComplianceGuard remain web-first features in this release.
