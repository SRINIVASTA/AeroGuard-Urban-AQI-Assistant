"""Indian CPCB Sub-Index AQI Calculator & Atmospheric Dispersion Analyzer."""

import json
from pathlib import Path
from typing import Dict, Any, List


def load_thresholds() -> List[Dict[str, Any]]:
    """Loads CPCB AQI breakpoint definitions from config/aqi_thresholds.json."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "aqi_thresholds.json"
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)["cpcb_breakpoints"]


def _calc_linear_subindex(conc: float, breakpoints: List[tuple]) -> int:
    """Computes linear interpolated sub-index per CPCB National AQI methodology."""
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= conc <= c_high:
            return round(((i_high - i_low) / (c_high - c_low)) * (conc - c_low) + i_low)
    return 500 if conc > breakpoints[-1][1] else 0


def compute_cpcb_aqi(pollutants: Dict[str, float]) -> Dict[str, Any]:
    """Calculates overall CPCB AQI, dominant pollutant, and health tier."""
    pm25_bp = [(0, 30, 0, 50), (30.01, 60, 51, 100), (60.01, 90, 101, 200),
               (90.01, 120, 201, 300), (120.01, 250, 301, 400), (250.01, 500, 401, 500)]
    pm10_bp = [(0, 50, 0, 50), (50.01, 100, 51, 100), (100.01, 250, 101, 200),
               (250.01, 350, 201, 300), (350.01, 430, 301, 400), (430.01, 600, 401, 500)]
    no2_bp = [(0, 40, 0, 50), (40.01, 80, 51, 100), (80.01, 180, 101, 200),
              (180.01, 280, 201, 300), (280.01, 400, 301, 400), (400.01, 800, 401, 500)]
    o3_bp = [(0, 50, 0, 50), (50.01, 100, 51, 100), (100.01, 168, 101, 200),
             (168.01, 208, 201, 300), (208.01, 748, 301, 400), (748.01, 1000, 401, 500)]

    sub_indices = {
        "PM2.5": _calc_linear_subindex(pollutants.get("pm2_5", 0.0), pm25_bp),
        "PM10": _calc_linear_subindex(pollutants.get("pm10", 0.0), pm10_bp),
        "NO2": _calc_linear_subindex(pollutants.get("no2", 0.0), no2_bp),
        "O3": _calc_linear_subindex(pollutants.get("o3", 0.0), o3_bp),
    }

    dominant_pollutant = max(sub_indices, key=sub_indices.get)
    overall_aqi = sub_indices[dominant_pollutant]

    matched_tier = load_thresholds()[-1]
    for tier in load_thresholds():
        if tier["min_aqi"] <= overall_aqi <= tier["max_aqi"]:
            matched_tier = tier
            break

    return {
        "aqi": overall_aqi,
        "dominant_pollutant": dominant_pollutant,
        "sub_indices": sub_indices,
        "category": matched_tier["category"],
        "color": matched_tier["color"],
        "health_impact": matched_tier["health_impact"],
        "general_advisory": matched_tier["general_advisory"],
    }


def analyze_dispersion(meteorology: Dict[str, float]) -> Dict[str, str]:
    """Evaluates atmospheric ventilation and stagnation risk from wind and boundary layer."""
    wind_ms = meteorology.get("wind_speed_kmh", 0.0) / 3.6
    blh = meteorology.get("boundary_layer_m", 500.0)
    ventilation_index = wind_ms * blh

    if ventilation_index < 1500:
        status = "High Stagnation Risk (Trapped Emissions)"
        summary = "Low wind speed and shallow mixing layer trap surface particulates near ground level."
    elif ventilation_index < 4500:
        status = "Moderate Atmospheric Dispersion"
        summary = "Steady airflow provides partial dilution of vehicular and industrial plumes."
    else:
        status = "Strong Ventilation & Rapid Clearing"
        summary = "High boundary layer and brisk winds actively disperse urban pollutants."

    return {
        "ventilation_index": f"{round(ventilation_index)} m²/s",
        "dispersion_status": status,
        "dispersion_summary": summary,
    }
