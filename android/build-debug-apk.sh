#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f gradlew ]]; then echo "gradlew not found" >&2; exit 1; fi
if [[ -z "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ]]; then
  echo "Set ANDROID_HOME or ANDROID_SDK_ROOT to your Android SDK path." >&2
  exit 1
fi
chmod +x gradlew
./gradlew --no-daemon clean assembleDebug
APK="app/build/outputs/apk/debug/app-debug.apk"
if [[ ! -f "$APK" ]]; then echo "APK not found at $APK" >&2; exit 1; fi
cp "$APK" ../ClearPathNexus-debug.apk
printf 'Built: %s\n' "$(cd .. && pwd)/ClearPathNexus-debug.apk"
