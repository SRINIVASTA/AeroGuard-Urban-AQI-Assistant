"""100% Dynamic Worldwide Location & Coordinate Resolver with Multi-Provider Fallback."""

from typing import Dict, Any
import requests

HEADERS = {
    "User-Agent": "AeroGuard-Urban-AQI-Assistant/1.0 (contact: tasrinivass@gmail.com)",
    "Accept": "application/json",
}


def resolve_location(query: str) -> Dict[str, Any]:
    """Dynamically resolves any typed city, town, or village worldwide via live geocoding."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Please type a city, town, or location name.")

    # Provider 1: Open-Meteo Global Geocoding API
    om_error = ""
    try:
        om_url = "https://open-meteo.com"
        om_params = {"name": cleaned, "count": 1, "language": "en", "format": "json"}
        resp = requests.get(om_url, params=om_params, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            top = results[0]
            parts = [top.get("name", ""), top.get("admin1", ""), top.get("country", "")]
            full_name = ", ".join(dict.fromkeys([p for p in parts if p]))
            return {
                "name": full_name or cleaned,
                "lat": float(top["latitude"]),
                "lon": float(top["longitude"]),
                "zone": f"Elevation {top.get('elevation', 'N/A')}m | Country: {top.get('country_code', 'N/A')}",
                "is_land": True,
            }
    except Exception as err:  # pylint: disable=broad-except
        om_error = str(err)

    # Provider 2 Fallback: OpenStreetMap Nominatim
    try:
        nom_url = "https://openstreetmap.org"
        nom_params = {"q": cleaned, "format": "json", "limit": 1}
        nom_resp = requests.get(nom_url, params=nom_params, headers=HEADERS, timeout=12)
        nom_resp.raise_for_status()
        nom_results = nom_resp.json()
        if nom_results:
            item = nom_results[0]
            return {
                "name": item.get("display_name", cleaned),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "zone": f"OSM Class: {item.get('type', 'Urban').title()}",
                "is_land": True,
            }
    except Exception as nom_err:  # pylint: disable=broad-except
        raise RuntimeError(f"Geocoding failed ({om_error} | {nom_err})") from nom_err

    raise ValueError(f"No worldwide location found for '{cleaned}'. Check spelling or switch to Lat/Lon.")


def resolve_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """Dynamically reverse-geocodes any typed Latitude & Longitude worldwide in real time."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("Latitude must be between -90 and 90, and Longitude between -180 and 180.")

    bdc_url = "https://bigdatacloud.net"
    params = {"latitude": lat, "longitude": lon, "localityLanguage": "en"}
    resp = requests.get(bdc_url, params=params, headers=HEADERS, timeout=12)
    resp.raise_for_status()
    info = resp.json()

    locality = info.get("locality") or info.get("city") or ""
    region = info.get("principalSubdivision") or ""
    country = info.get("countryName") or ""

    if not country:
        display_name = f"Offshore / Marine Grid ({lat:.4f}, {lon:.4f})"
        zone = "Open Ocean / Marine Sector"
        is_land = False
    else:
        parts = [p for p in [locality, region, country] if p]
        display_name = ", ".join(dict.fromkeys(parts))
        zone = f"Admin Region: {region or country}"
        is_land = True

    return {
        "name": display_name,
        "lat": float(lat),
        "lon": float(lon),
        "zone": zone,
        "is_land": is_land,
    }
