"""Pytest verification suite covering CPCB AQI math, dispersion, geocoding, and PDF generation."""

import pytest
from src.dispersion_analyzer import compute_cpcb_aqi, analyze_dispersion
from src.geocoder import resolve_location
from src.gemini_advisor import generate_persona_advisory
from src.pdf_reporter import build_aqi_certificate


def test_cpcb_aqi_good_category():
    pollutants = {"pm2_5": 15.0, "pm10": 30.0, "no2": 20.0, "o3": 25.0}
    report = compute_cpcb_aqi(pollutants)
    assert report["aqi"] <= 50
    assert report["category"] == "Good"


def test_cpcb_aqi_poor_category():
    pollutants = {"pm2_5": 105.0, "pm10": 140.0, "no2": 45.0, "o3": 30.0}
    report = compute_cpcb_aqi(pollutants)
    assert 201 <= report["aqi"] <= 300
    assert report["dominant_pollutant"] == "PM2.5"
    assert report["category"] == "Poor"


def test_dispersion_stagnation_detection():
    stagnant = analyze_dispersion({"wind_speed_kmh": 3.6, "boundary_layer_m": 300.0})
    assert "Stagnation" in stagnant["dispersion_status"]


def test_preset_city_resolution():
    loc = resolve_location("Visakhapatnam")
    assert loc["is_land"] is True
    assert pytest.approx(loc["lat"], 0.1) == 17.68


def test_empty_location_raises():
    with pytest.raises(ValueError):
        resolve_location("   ")


def test_offline_persona_advisory_and_pdf_output():
    loc = resolve_location("Visakhapatnam")
    telemetry = {
        "pollutants": {"pm2_5": 68.0, "pm10": 115.0, "no2": 32.0, "so2": 12.0, "o3": 48.0, "co": 410.0},
        "meteorology": {"temp_c": 29.5, "humidity_pct": 72.0, "wind_speed_kmh": 14.0, "wind_dir_deg": 180.0, "boundary_layer_m": 850.0},
    }
    aqi_report = compute_cpcb_aqi(telemetry["pollutants"])
    dispersion = analyze_dispersion(telemetry["meteorology"])
    advisory = generate_persona_advisory(loc["name"], aqi_report, dispersion, persona="General Citizen", api_key="")
    assert len(advisory) > 20

    pdf_bytes = build_aqi_certificate(loc, telemetry, aqi_report, dispersion, advisory, "General Citizen")
    assert pdf_bytes.startswith(b"%PDF")
