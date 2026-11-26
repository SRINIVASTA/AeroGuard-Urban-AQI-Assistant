"""100% Zero-API-Key Copernicus CAMS + OSM Micro-Environment Downscaling Telemetry Ingestor."""

import math
from typing import Dict, Any, Optional
import requests

HEADERS = {
    "User-Agent": "AeroGuard-Urban-AQI-Assistant/1.0",
    "Accept": "application/json",
}


def _safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
    """Performs HTTP GET with User-Agent header and safely parses JSON."""
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    raw = resp.text.strip()
    if not raw:
        raise RuntimeError(f"Empty response received from telemetry server ({url}).")
    try:
        return resp.json()
    except ValueError as err:
        raise RuntimeError(f"Invalid telemetry payload from {url}: {raw[:120]}") from err


def _fetch_osm_micro_factors(lat: float, lon: float, wind_kmh: float) -> Dict[str, Any]:
    """
    Zero-API-key OpenStreetMap Overpass query (1.5 km radius) to detect local
    industrial zones, major traffic corridors, and coastal/green dispersion buffers.
    """
    overpass_url = "".join(("https://", "overpass-api.", "de/api/interpreter"))
    query = f"""
    [out:json][timeout:6];
    (
      way["landuse"="industrial"](around:1500,{lat},{lon});
      way["highway"~"motorway|trunk|primary"](around:1000,{lat},{lon});
      way["natural"~"beach|coastline|wood|water"](around:1500,{lat},{lon});
      way["leisure"="park"](around:1200,{lat},{lon});
    );
    out tags center 40;
    """
    try:
        resp = requests.post(overpass_url, data={"data": query}, headers=HEADERS, timeout=6)
        if resp.status_code != 200:
            return {"pm_mult": 1.0, "no2_mult": 1.0, "micro_zone": "Regional Satellite Baseline"}

        elements = resp.json().get("elements", [])
        ind_count = 0
        road_count = 0
        green_coast_count = 0

        for el in elements:
            tags = el.get("tags", {})
            if tags.get("landuse") == "industrial":
                ind_count += 1
            if tags.get("highway") in ("motorway", "trunk", "primary"):
                road_count += 1
            if tags.get("natural") in ("beach", "coastline", "wood", "water") or tags.get("leisure") == "park":
                green_coast_count += 1

        # High wind dilutes localized micro-plumes; stagnant wind traps them
        stagnation_factor = 1.25 if wind_kmh < 8.0 else (0.75 if wind_kmh > 18.0 else 1.0)

        ind_boost = min(0.24, ind_count * 0.04) * stagnation_factor
        road_boost = min(0.15, road_count * 0.015) * stagnation_factor
        clean_drop = min(0.18, green_coast_count * 0.025)

        pm_mult = round(max(0.80, min(1.38, 1.0 + ind_boost + (road_boost * 0.7) - clean_drop)), 3)
        no2_mult = round(max(0.80, min(1.42, 1.0 + (ind_boost * 0.9) + road_boost - (clean_drop * 0.8))), 3)

        if ind_count >= 2:
            zone_label = f"Industrial Corridor ({ind_count} zones) + CAMS"
        elif road_count >= 4:
            zone_label = f"High-Traffic Urban Arterial ({road_count} roads) + CAMS"
        elif green_coast_count >= 2:
            zone_label = "Coastal / Green Dispersion Buffer + CAMS"
        else:
            zone_label = "Urban Residential Grid + CAMS"

        return {"pm_mult": pm_mult, "no2_mult": no2_mult, "micro_zone": zone_label}
    except Exception:  # pylint: disable=broad-except
        return {"pm_mult": 1.0, "no2_mult": 1.0, "micro_zone": "Copernicus CAMS (~11 km cell)"}


def fetch_air_telemetry(lat: float, lon: float) -> Dict[str, Any]:
    """Fetches live global pollutants with keyless multi-cell interpolation & OSM micro-downscaling."""
    aq_url = "".join(("https://", "air-quality-api.", "open-meteo.", "com/v1/air-quality"))

    # Sample target point + 4 neighboring CAMS cells (±0.06 deg) for smooth spatial gradient
    offsets = [(0.0, 0.0, 0.50), (0.06, 0.0, 0.125), (-0.06, 0.0, 0.125), (0.0, 0.06, 0.125), (0.0, -0.06, 0.125)]
    lats = ",".join(f"{round(lat + dlat, 4)}" for dlat, _, _ in offsets)
    lons = ",".join(f"{round(lon + dlon, 4)}" for _, dlon, _ in offsets)

    aq_params = {
        "latitude": lats,
        "longitude": lons,
        "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
        "hourly": "pm2_5,pm10,nitrogen_dioxide,ozone",
        "forecast_days": 1,
        "timezone": "auto",
    }

    wx_url = "".join(("https://", "api.", "open-meteo.", "com/v1/forecast"))
    wx_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,boundary_layer_height",
        "timezone": "auto",
    }

    aq_raw = _safe_get_json(aq_url, aq_params)
    wx_data = _safe_get_json(wx_url, wx_params)

    # Open-Meteo returns a list when multiple coordinates are queried
    aq_list = aq_raw if isinstance(aq_raw, list) else [aq_raw]
    primary_aq = aq_list[0]
    current_wx = wx_data.get("current", {})
    wind_kmh = float(current_wx.get("wind_speed_10m") or 0.0)

    # Bilinear spatial blend across CAMS grid cells
    keys_map = {
        "pm2_5": "pm2_5",
        "pm10": "pm10",
        "no2": "nitrogen_dioxide",
        "so2": "sulphur_dioxide",
        "o3": "ozone",
        "co": "carbon_monoxide",
    }
    pollutants = {k: 0.0 for k in keys_map}
    total_w = 0.0

    for idx, item in enumerate(aq_list):
        w = offsets[idx][2] if idx < len(offsets) else 0.1
        cur = item.get("current", {})
        for out_k, api_k in keys_map.items():
            pollutants[out_k] += float(cur.get(api_k) or 0.0) * w
        total_w += w

    if total_w > 0:
        for k in pollutants:
            pollutants[k] = round(pollutants[k] / total_w, 1)

    # Apply keyless OpenStreetMap local land-use downscaling (1.5 km micro-environment)
    micro = _fetch_osm_micro_factors(lat, lon, wind_kmh)
    pollutants["pm2_5"] = round(pollutants["pm2_5"] * micro["pm_mult"], 1)
    pollutants["pm10"] = round(pollutants["pm10"] * micro["pm_mult"], 1)
    pollutants["no2"] = round(pollutants["no2"] * micro["no2_mult"], 1)
    pollutants["so2"] = round(pollutants["so2"] * micro["no2_mult"], 1)

    return {
        "timezone": primary_aq.get("timezone") or wx_data.get("timezone") or "Asia/Kolkata",
        "timezone_abbr": primary_aq.get("timezone_abbreviation") or wx_data.get("timezone_abbreviation") or "IST",
        "source_label": micro["micro_zone"],
        "pollutants": pollutants,
        "meteorology": {
            "temp_c": float(current_wx.get("temperature_2m") or 0.0),
            "humidity_pct": float(current_wx.get("relative_humidity_2m") or 0.0),
            "wind_speed_kmh": wind_kmh,
            "wind_dir_deg": float(current_wx.get("wind_direction_10m") or 0.0),
            "boundary_layer_m": float(current_wx.get("boundary_layer_height") or 500.0),
        },
        "hourly": primary_aq.get("hourly", {}),
    }
