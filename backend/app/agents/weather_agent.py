"""
Weather Agent — integrates with OpenWeatherMap API.
"""
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, date
import asyncio

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.config import settings


class WeatherAgent(BaseAgent):
    """Agent for fetching weather forecasts."""
    
    agent_type = "weather"
    dependencies = []  # Weather is independent
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.api_key = config.get("openweathermap_api_key") if config else settings.openweathermap_api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Get weather forecast for a location and date.
        
        Expected parameters:
        - location: str (city name or "lat,lng")
        - date: str (ISO date, default: today)
        - units: str (metric/imperial, default: metric)
        """
        start_time = datetime.utcnow()
        
        try:
            location = request.parameters.get("location", "Moscow")
            date_str = request.parameters.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
            units = request.parameters.get("units", "metric")
            
            # Check if we have cached data
            cache_key = f"weather:{location}:{date_str}"
            cached = await self._get_cache(cache_key)
            if cached:
                return AgentResponse(
                    success=True,
                    data=cached,
                    confidence=0.9,
                    processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
                )
            
            # Get coordinates if location is a city name
            if "," in location:
                lat, lon = map(float, location.split(","))
            else:
                # Geocoding request
                lat, lon = await self._geocode(location)
            
            # Fetch weather
            weather_data = await self._fetch_weather(lat, lon, units)
            
            # Format response
            result = {
                "location": location,
                "date": date_str,
                "forecast": self._format_forecast(weather_data, date_str),
                "temperature": weather_data.get("main", {}).get("temp"),
                "feels_like": weather_data.get("main", {}).get("feels_like"),
                "humidity": weather_data.get("main", {}).get("humidity"),
                "wind_speed": weather_data.get("wind", {}).get("speed"),
                "description": weather_data.get("weather", [{}])[0].get("description"),
                "icon": weather_data.get("weather", [{}])[0].get("icon")
            }
            
            # Cache for 1 hour
            await self._save_cache(cache_key, result, ttl=3600)
            
            return AgentResponse(
                success=True,
                data=result,
                confidence=0.95,
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                data={},
                error=str(e),
                confidence=0.0,
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
    
    async def _geocode(self, city: str) -> tuple[float, float]:
        """Convert city name to coordinates."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/geo/1.0/direct",
                params={
                    "q": city,
                    "limit": 1,
                    "appid": self.api_key
                }
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                raise ValueError(f"City '{city}' not found")
            return data[0]["lat"], data[0]["lon"]
    
    async def _fetch_weather(self, lat: float, lon: float, units: str) -> Dict[str, Any]:
        """Fetch current weather from OpenWeatherMap."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "units": units,
                    "appid": self.api_key
                }
            )
            response.raise_for_status()
            return response.json()
    
    def _format_forecast(self, data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """Format weather data into a simplified forecast."""
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        
        return {
            "temp_current": main.get("temp"),
            "temp_min": main.get("temp_min"),
            "temp_max": main.get("temp_max"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "wind_speed": wind.get("speed"),
            "wind_deg": wind.get("deg"),
            "description": weather.get("description"),
            "icon": weather.get("icon"),
            "cloudiness": data.get("clouds", {}).get("all")
        }
    
    async def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response (simplified, use Redis in production)."""
        # TODO: Implement Redis cache
        return None
    
    async def _save_cache(self, key: str, value: Dict[str, Any], ttl: int = 3600):
        """Save to cache (simplified, use Redis in production)."""
        # TODO: Implement Redis cache
        pass