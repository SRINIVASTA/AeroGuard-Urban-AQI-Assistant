"""Location resolver with OpenStreetMap Nominatim and offshore/marine validation."""

from typing import Dict, Any
import requests


DEFAULT_CITIES: Dict[str, Dict[str, Any]] = {
    "Visakhapatnam": {
        "name": "Visakhapatnam, Andhra Pradesh, India",
        "lat": 17.6868,
        "lon": 83.2185,
        "zone": "Coastal Industrial & Port Corridor",
    },
    "New Delhi": {
        "name": "New Delhi, Delhi, India",
        "lat": 28.6139,
        "lon": 77.2090,
        "zone": "Indo-Gangetic Urban Basin",
    },
    "Bengaluru": {
        "name": "Bengaluru, Karnataka, India",
        "lat": 12.9716,
        "lon": 77.5946,
        "zone": "Deccan Plateau Tech Hub",
    },
    "Mumbai": {
        "name": "Mumbai, Maharashtra, India",
        "lat": 19.0760,
        "lon": 72.8777,
        "zone": "Western Coastal Metropolis",
    },
    "Hyderabad": {
        "name": "Hyderabad, Telangana, India",
        "lat": 17.3850,
        "lon": 78.4867,
        "zone": "Telangana Urban Agglomeration",
    },
}


def resolve_location(query: str) -> Dict[str, Any]:
    """Resolves a city or neighborhood string to validated terrestrial coordinates."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Location query cannot be empty.")

    for preset_key, preset_data in DEFAULT_CITIES.items():
        if cleaned.lower() == preset_key.lower():
            return {**preset_data, "is_land": True}

    url = "https://openstreetmap.org"
    params = {"q": cleaned, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "AeroGuard-Urban-AQI-Assistant/1.0"}

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    results = response.json()

    if not results:
        raise ValueError(f"Could not resolve urban location for '{cleaned}'.")

    top = results[0]
    place_class = top.get("class", "")
    place_type = top.get("type", "")
    if place_class == "natural" and place_type in {"water", "sea", "ocean", "bay"}:
        raise ValueError("Selected coordinates fall in an offshore marine zone.")

    return {
        "name": top.get("display_name", cleaned),
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "zone": top.get("type", "Urban Zone").replace("_", " ").title(),
        "is_land": True,
    }
