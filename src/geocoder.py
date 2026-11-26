"""100% Dynamic Worldwide Location & Coordinate Resolver with Multi-Provider Fallback."""

from typing import Dict, Any
import requests

HEADERS = {
    "User-Agent": "AeroGuard-Urban-AQI-Assistant/1.0 (https://github.com)",
    "Accept": "application/json",
}


def _safe_json(resp: requests.Response, source_name: str) -> Dict[str, Any]:
    """Safely parses HTTP JSON response with clear diagnostics."""
    resp.raise_for_status()
    raw = resp.text.strip()
    if not raw:
        raise RuntimeError(f"{source_name} returned an empty response.")
    try:
        return resp.json()
    except ValueError as err:
        raise RuntimeError(f"{source_name} returned non-JSON payload: {raw[:100]}") from err


def resolve_location(query: str) -> Dict[str, Any]:
    """Dynamically resolves any typed city, town, or village worldwide via live geocoding."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Please type a city, town, or location name.")

    # Provider 1: Open-Meteo Global Geocoding API
    try:
        om_url = "https://open-meteo.com"
        om_params = {"name": cleaned, "count": 1, "language": "en", "format": "json"}
        resp = requests.get(om_url, params=om_params, headers=HEADERS, timeout=12)
        data = _safe_json(resp, "Open-Meteo Geocoder")
        results = data.get("results", [])
        if results:
            top = results
            parts = [top.get("name", ""), top.get("admin1", ""), top.get("country", "")]
            full_name = ", ".join(dict.fromkeys([p for p in parts if p]))
            return {
                "name": full_name or cleaned,
                "lat": float(top["latitude"]),
                "lon": float(top["longitude"]),
                "zone": f"Elevation {top.get('elevation', 'N/A')}m | Country: {top.get('country_code', 'N/A')}",
                "is_land": True,
            }
    except Exception:  # pylint: disable=broad-except
        pass

    # Provider 2 Fallback: Photon (OpenStreetMap Elastic Geocoder - Cloud-friendly)
    ph_url = "https://komoot.io"
    ph_params = {"q": cleaned, "limit": 1, "lang": "en"}
    ph_resp = requests.get(ph_url, params=ph_params, headers=HEADERS, timeout=12)
    ph_data = _safe_json(ph_resp, "Photon Geocoder")
    features = ph_data.get("features", [])
    if not features:
        raise ValueError(f"No worldwide location found for '{cleaned}'. Try another spelling or use Lat/Lon mode.")

    feat = features
    coords = feat["geometry"]["coordinates"]  # [lon, lat]
    props = feat.get("properties", {})
    parts = [props.get("name", ""), props.get("state", ""), props.get("country", "")]
    full_name = ", ".join(dict.fromkeys([p for p in parts if p]))

    return {
        "name": full_name or cleaned,
        "lat": float(coords[1]),
        "lon": float(coords),
        "zone": f"OSM Type: {props.get('osm_value', 'Urban').title()}",
        "is_land": True,
    }


def resolve_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """Dynamically reverse-geocodes any typed Latitude & Longitude worldwide in real time."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("Latitude must be between -90 and 90, and Longitude between -180 and 180.")

    bdc_url = "https://bigdatacloud.net"
    params = {"latitude": lat, "longitude": lon, "localityLanguage": "en"}
    resp = requests.get(bdc_url, params=params, headers=HEADERS, timeout=12)
    info = _safe_json(resp, "BigDataCloud Reverse Geocoder")

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
