# Android API 23 Build Notes

The Android client is configured with:

- `minSdk = 23`
- `targetSdk = 35`
- `compileSdk = 35`
- Android Gradle Plugin 8.7.2
- Gradle 8.9
- Kotlin 2.0.21
- Java/Kotlin bytecode target 17
- core-library desugaring enabled

Supabase Kotlin documents Android API 26 as its normal minimum; lower Android versions require core-library desugaring. The project enables that path with `com.android.tools:desugar_jdk_libs:2.0.3`.

Build:

```bash
./gradlew clean assembleDebug bundleRelease
```

Before a release build, replace the placeholder `API_BASE_URL` in the `release` build type with the deployed HTTPS backend URL.
