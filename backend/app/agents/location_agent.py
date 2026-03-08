"""
Location Agent — integrates with Google Places API (or alternatives).
"""
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.config import settings


class LocationAgent(BaseAgent):
    """Agent for finding places (restaurants, parks, cafes, etc.)."""
    
    agent_type = "location"
    dependencies = []  # Independent
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.api_key = config.get("google_places_api_key") if config else settings.google_places_api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Find places near a location.
        
        Expected parameters:
        - location: str (city name or coordinates)
        - place_type: str (restaurant, cafe, park, museum, etc.)
        - radius: int (meters, default: 5000)
        - budget: float (optional, for filtering)
        - limit: int (max results, default: 10)
        """
        start_time = datetime.utcnow()
        
        try:
            location = request.parameters.get("location", "")
            place_type = request.parameters.get("place_type", "restaurant")
            radius = request.parameters.get("radius", 5000)
            budget = request.parameters.get("budget")
            limit = request.parameters.get("limit", 10)
            
            # Get coordinates if needed
            if "," in location:
                lat, lng = map(float, location.split(","))
            else:
                # Use geocoding (could call OpenWeatherMap's geocoder)
                lat, lng = await self._geocode(location)
            
            # Query Google Places API
            places = await self._search_places(lat, lng, place_type, radius, limit)
            
            # Filter by budget if provided (estimate from price_level)
            if budget is not None:
                places = self._filter_by_budget(places, budget)
            
            # Format response
            result = {
                "location": location,
                "coordinates": {"lat": lat, "lng": lng},
                "place_type": place_type,
                "places": places[:limit],
                "total_found": len(places)
            }
            
            return AgentResponse(
                success=True,
                data=result,
                confidence=0.9,
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
        """Simple geocoding using OpenWeatherMap (free)."""
        # Reuse OpenWeatherMap geocoding API (it's free)
        # In production, use Google Geocoding for better accuracy
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={
                    "q": city,
                    "limit": 1,
                    "appid": settings.openweathermap_api_key
                }
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                raise ValueError(f"City '{city}' not found")
            return data[0]["lat"], data[0]["lon"]
    
    async def _search_places(
        self,
        lat: float,
        lng: float,
        place_type: str,
        radius: int,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search places using Google Places API."""
        if not self.api_key:
            raise ValueError("Google Places API key not configured")
        
        # Map our types to Google Places types
        type_mapping = {
            "restaurant": "restaurant",
            "cafe": "cafe",
            "park": "park",
            "museum": "museum",
            "theater": "theater",
            "bank": "bank",
            "atm": "atm",
            "supermarket": "supermarket"
        }
        
        google_type = type_mapping.get(place_type, place_type)
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/nearbysearch/json",
                params={
                    "location": f"{lat},{lng}",
                    "radius": radius,
                    "type": google_type,
                    "key": self.api_key,
                    "language": "ru"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            places = []
            for place in data.get("results", [])[:limit]:
                places.append({
                    "id": place.get("place_id"),
                    "name": place.get("name"),
                    "address": place.get("vicinity") or place.get("formatted_address"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("user_ratings_total"),
                    "price_level": place.get("price_level"),  # 0-4
                    "coordinates": place.get("geometry", {}).get("location"),
                    "types": place.get("types", []),
                    "photos": place.get("photos", [])
                })
            
            return places
    
    def _filter_by_budget(self, places: List[Dict[str, Any]], budget: float) -> List[Dict[str, Any]]:
        """Filter places by estimated budget."""
        # Very rough estimation: price_level 0-4 → budget_multiplier
        # This is a simplification; in reality you'd need price ranges per place
        if budget < 1000:  # Tight budget → price_level 0-1
            return [p for p in places if p.get("price_level", 2) <= 1]
        elif budget < 3000:  # Medium budget → price_level 0-2
            return [p for p in places if p.get("price_level", 2) <= 2]
        else:  # High budget → any
            return places