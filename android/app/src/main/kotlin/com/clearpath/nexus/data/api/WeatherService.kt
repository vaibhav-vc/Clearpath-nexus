package com.clearpath.nexus.data.api

import com.clearpath.nexus.data.model.WeatherCondition
import org.json.JSONObject

/**
 * Maps backend weather responses into the Android weather model.
 * Maps OWM weather codes to our condition legend symbols.
 */
object WeatherService {

    suspend fun fetchWeather(lat: Double, lon: Double): WeatherCondition? {
        return try {
            val response = BackendApiClient.get("/weather/environmental?lat=$lat&lon=$lon")
            val weather = JSONObject(response).optJSONObject("weather") ?: return null
            parseResponse(weather.toString())
        } catch (_: Exception) {
            null
        }
    }

    private fun parseResponse(json: String): WeatherCondition? {
        return try {
            val root = JSONObject(json)
            val main = root.getJSONObject("main")
            val wind = root.getJSONObject("wind")
            val weatherArr = root.getJSONArray("weather")
            if (weatherArr.length() == 0) return null

            val w = weatherArr.getJSONObject(0)
            val code = w.getInt("id")
            val desc = w.getString("description")
                .replaceFirstChar { it.uppercaseChar() }

            val (emoji, label) = mapWeatherCode(code)

            WeatherCondition(
                temp = main.getDouble("temp"),
                humidity = main.getInt("humidity"),
                windSpeed = wind.getDouble("speed"),
                description = desc,
                iconEmoji = emoji,
                conditionLabel = label,
            )
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Maps OWM weather condition codes to our legend emoji and label.
     * See: https://openweathermap.org/weather-conditions
     */
    private fun mapWeatherCode(code: Int): Pair<String, String> = when (code) {
        in 200..232 -> "⛈️" to "Thunderstorm"
        in 300..321 -> "🌦️" to "Light Rain"
        in 500..504 -> "🌧️" to "Heavy Rain"
        511         -> "🧊" to "Icing Risk"
        in 520..531 -> "🌧️" to "Heavy Rain"
        in 600..622 -> "🌨️" to "Snow"
        701         -> "🌁" to "Mist"
        711         -> "🏭" to "Smoke"
        721         -> "🌁" to "Haze"
        731, 761    -> "💨" to "Dust Haze"
        741         -> "🌫️" to "Fog"
        751         -> "💨" to "Sand"
        762         -> "🌋" to "Volcanic Ash"
        771         -> "🌬️" to "Squall"
        781         -> "🌀" to "Tornado"
        800         -> "☀️" to "Clear"
        801         -> "⛅" to "Partly Cloudy"
        in 802..804 -> "☁️" to "Cloudy"
        else        -> "🌡️" to "Unknown"
    }

    /**
     * Converts a weather condition into a 0–100 score.
     * Clear/mild = high score. Severe = low score.
     */
    fun weatherToScore(condition: WeatherCondition?): Int {
        if (condition == null) return 50
        var score = 100

        // Temperature penalties
        if (condition.temp > 45) score -= 25
        else if (condition.temp > 40) score -= 15
        else if (condition.temp < 0) score -= 20
        else if (condition.temp < 5) score -= 10

        // Wind penalties
        if (condition.windSpeed > 20) score -= 30
        else if (condition.windSpeed > 12) score -= 15
        else if (condition.windSpeed > 8) score -= 5

        // Humidity penalties
        if (condition.humidity > 90) score -= 10
        else if (condition.humidity < 15) score -= 5

        // Condition-based penalties
        score -= when (condition.conditionLabel) {
            "Thunderstorm" -> 35
            "Heavy Rain" -> 25
            "Snow" -> 30
            "Icing Risk" -> 35
            "Fog" -> 20
            "Light Rain" -> 10
            "Mist" -> 5
            "Dust Haze" -> 15
            "Squall" -> 25
            "Tornado" -> 50
            "Clear", "Partly Cloudy" -> 0
            "Cloudy" -> 3
            else -> 5
        }

        return score.coerceIn(0, 100)
    }
}
