# ClearPath Nexus — Production ProGuard / R8 Rules

# 1. Kotlinx Serialization
-keepattributes *Annotation*, InnerClasses, Signature
-keepclassmembers class * {
    @kotlinx.serialization.Serializable <fields>;
}
-keepclassmembers class * {
    @kotlinx.serialization.SerialName <fields>;
}
-keepclassmembers class * {
    *** Companion;
}
-keepclasseswithmembers class * {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,allowobfuscation,allowshrinking class com.clearpath.nexus.data.model.** { *; }

# 2. Ktor HTTP Client & Engines
-keep class io.ktor.** { *; }
-dontwarn io.ktor.**
-keep class kotlinx.coroutines.** { *; }
-dontwarn kotlinx.coroutines.**

# 3. OSMDroid Maps
-keep class org.osmdroid.** { *; }
-dontwarn org.osmdroid.**

# 4. AndroidX Jetpack Compose & Lifecycle
-keep class androidx.compose.** { *; }
-dontwarn androidx.compose.**
-keep class androidx.lifecycle.** { *; }
-keepclassmembers class * extends androidx.lifecycle.ViewModel {
    <init>(...);
}
