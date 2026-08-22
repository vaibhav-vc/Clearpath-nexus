package com.clearpath.nexus.data.api

import com.clearpath.nexus.BuildConfig
import io.github.jan.supabase.auth.auth
import io.ktor.client.HttpClient
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.client.statement.HttpResponse
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.http.HttpStatusCode
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

object BackendApiClient {
    // 10.0.2.2 points to host localhost in Android Emulator
    private val baseUrl = BuildConfig.BACKEND_BASE_URL.trimEnd('/')

    val jsonConfig = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    private val client = HttpClient(Android) {
        engine {
            connectTimeout = 10_000
            socketTimeout = 15_000
        }
    }

    suspend fun get(path: String): String {
        return getInternal(path, allowRefresh = true)
    }

    private suspend fun getInternal(path: String, allowRefresh: Boolean): String {
        val url = if (path.startsWith("http")) path else "$baseUrl$path"
        val response = client.get(url) {
            SupabaseClient.client.auth.currentSessionOrNull()?.accessToken?.let {
                header("Authorization", "Bearer $it")
            }
        }
        return response.requireSuccess()
    }

    suspend fun postJson(path: String, jsonBody: String): String {
        return postJsonInternal(path, jsonBody, allowRefresh = true)
    }

    private suspend fun postJsonInternal(path: String, jsonBody: String, allowRefresh: Boolean): String {
        val url = if (path.startsWith("http")) path else "$baseUrl$path"
        val response = client.post(url) {
            contentType(ContentType.Application.Json)
            SupabaseClient.client.auth.currentSessionOrNull()?.accessToken?.let {
                header("Authorization", "Bearer $it")
            }
            setBody(jsonBody)
        }
        return response.requireSuccess()
    }

    private suspend fun HttpResponse.requireSuccess(): String {
        val body = bodyAsText()
        if (status.value !in 200..299) {
            throw IllegalStateException("Backend request failed (${status.value}): $body")
        }
        return body
    }
}
