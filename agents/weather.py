import httpx

import config

_WMO = {
    0: "clear skies", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


def get_current_weather() -> dict:
    """Fetch current weather for the configured location. Returns a dict or raises."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": config.LOCATION_LAT,
        "longitude": config.LOCATION_LON,
        "current": "temperature_2m,apparent_temperature,weathercode,windspeed_10m,relative_humidity_2m",
        "timezone": "auto",
        "wind_speed_unit": "kmh",
    }
    resp = httpx.get(url, params=params, timeout=8)
    resp.raise_for_status()
    current = resp.json()["current"]
    code = current["weathercode"]
    return {
        "city": config.LOCATION_NAME,
        "condition": _WMO.get(code, "unknown conditions"),
        "temp_c": round(current["temperature_2m"]),
        "feels_like_c": round(current["apparent_temperature"]),
        "humidity": round(current["relative_humidity_2m"]),
        "wind_kmh": round(current["windspeed_10m"]),
    }


def weather_summary() -> str:
    """Return a spoken-friendly weather sentence, or an error string."""
    try:
        w = get_current_weather()
        return (
            f"Currently in {w['city']}: {w['condition']}, "
            f"{w['temp_c']} degrees Celsius, feels like {w['feels_like_c']}. "
            f"Humidity at {w['humidity']} percent, winds at {w['wind_kmh']} kilometres per hour."
        )
    except Exception as exc:
        return f"Weather data is currently unavailable. {exc}"
