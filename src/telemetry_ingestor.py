"""Zero-API-key Copernicus CAMS Air Quality & Meteorology Telemetry Ingestor."""

from typing import Dict, Any
import requests


def fetch_air_telemetry(lat: float, lon: float) -> Dict[str, Any]:
    """Fetches real-time pollutants (PM2.5, PM10, NO2, O3, SO2, CO) and wind vectors."""
    aq_url = "https://open-meteo.com"
    aq_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,european_aqi",
        "hourly": "pm2_5,pm10,nitrogen_dioxide,ozone",
        "forecast_days": 1,
        "timezone": "auto",
    }

    wx_url = "https://open-meteo.com"
    wx_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,boundary_layer_height",
        "timezone": "auto",
    }

    aq_resp = requests.get(aq_url, params=aq_params, timeout=12)
    aq_resp.raise_for_status()
    aq_data = aq_resp.json()

    wx_resp = requests.get(wx_url, params=wx_params, timeout=12)
    wx_resp.raise_for_status()
    wx_data = wx_resp.json()

    current_aq = aq_data.get("current", {})
    current_wx = wx_data.get("current", {})

    return {
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
