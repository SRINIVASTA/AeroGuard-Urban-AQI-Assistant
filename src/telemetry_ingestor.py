"""Zero-API-key Copernicus CAMS Air Quality & Meteorology Telemetry Ingestor."""

from typing import Dict, Any
import requests

HEADERS = {
    "User-Agent": "AeroGuard-Urban-AQI-Assistant/1.0",
    "Accept": "application/json",
}


def _safe_get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Performs HTTP GET with User-Agent header and safely parses JSON."""
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    raw = resp.text.strip()
    if not raw:
        raise RuntimeError(f"Empty response received from telemetry server ({url}).")
    try:
        return resp.json()
    except ValueError as err:
        raise RuntimeError(f"Invalid telemetry payload from {url}: {raw[:120]}") from err


def fetch_air_telemetry(lat: float, lon: float) -> Dict[str, Any]:
    """Fetches live global pollutants (PM2.5, PM10, NO2, O3, SO2, CO) and wind vectors."""
    aq_url = "".join(("https://", "air-quality-api.", "open-meteo.", "com/v1/air-quality"))
    aq_params = {
        "latitude": lat,
        "longitude": lon,
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

    aq_data = _safe_get_json(aq_url, aq_params)
    wx_data = _safe_get_json(wx_url, wx_params)

    current_aq = aq_data.get("current", {})
    current_wx = wx_data.get("current", {})

    return {
        "timezone": aq_data.get("timezone") or wx_data.get("timezone") or "Asia/Kolkata",
        "timezone_abbr": aq_data.get("timezone_abbreviation") or wx_data.get("timezone_abbreviation") or "IST",
        "pollutants": {
            "pm2_5": float(current_aq.get("pm2_5") or 0.0),
            "pm10": float(current_aq.get("pm10") or 0.0),
            "no2": float(current_aq.get("nitrogen_dioxide") or 0.0),
            "so2": float(current_aq.get("sulphur_dioxide") or 0.0),
            "o3": float(current_aq.get("ozone") or 0.0),
            "co": float(current_aq.get("carbon_monoxide") or 0.0),
        },
        "meteorology": {
            "temp_c": float(current_wx.get("temperature_2m") or 0.0),
            "humidity_pct": float(current_wx.get("relative_humidity_2m") or 0.0),
            "wind_speed_kmh": float(current_wx.get("wind_speed_10m") or 0.0),
            "wind_dir_deg": float(current_wx.get("wind_direction_10m") or 0.0),
            "boundary_layer_m": float(current_wx.get("boundary_layer_height") or 500.0),
        },
        "hourly": aq_data.get("hourly", {}),
    }
