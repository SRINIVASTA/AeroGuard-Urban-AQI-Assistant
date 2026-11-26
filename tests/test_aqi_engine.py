"""Pytest verification suite covering CPCB AQI math, dispersion, coordinate validation, and PDF generation."""

import re
import zlib
import pytest
from src.dispersion_analyzer import compute_cpcb_aqi, analyze_dispersion
from src.geocoder import resolve_location, resolve_coordinates
from src.gemini_advisor import generate_persona_advisory
from src.pdf_reporter import build_aqi_certificate
from src.alert_dispatcher import EnterpriseEmailService


def _extract_pdf_text_bytes(pdf_bytes: bytes) -> bytes:
    """Decompresses FlateDecode PDF streams so rendered text can be verified in tests."""
    chunks = [pdf_bytes]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        try:
            chunks.append(zlib.decompress(match.group(1)))
        except zlib.error:
            pass
    return b"\n".join(chunks)


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


def test_empty_location_and_invalid_coords_raise():
    with pytest.raises(ValueError):
        resolve_location("   ")
    with pytest.raises(ValueError):
        resolve_coordinates(120.0, 83.21)


def test_email_service_missing_credentials_raises():
    with pytest.raises(ValueError):
        EnterpriseEmailService.send_report(
            recipient_string="test@example.com",
            sender_email="",
            app_password="",
            pdf_bytes=b"%PDF-1.4 test",
        )


def test_offline_persona_advisory_and_pdf_output():
    loc = {
        "name": "Visakhapatnam, Andhra Pradesh, India",
        "lat": 17.6868,
        "lon": 83.2185,
        "zone": "Admin Region: Andhra Pradesh",
        "is_land": True,
    }
    telemetry = {
        "timezone": "Asia/Kolkata",
        "timezone_abbr": "IST",
        "pollutants": {"pm2_5": 68.0, "pm10": 115.0, "no2": 32.0, "so2": 12.0, "o3": 48.0, "co": 410.0},
        "meteorology": {"temp_c": 29.5, "humidity_pct": 72.0, "wind_speed_kmh": 14.0, "wind_dir_deg": 180.0, "boundary_layer_m": 850.0},
    }
    aqi_report = compute_cpcb_aqi(telemetry["pollutants"])
    dispersion = analyze_dispersion(telemetry["meteorology"])
    advisory = generate_persona_advisory(loc["name"], aqi_report, dispersion, persona="General Citizen", api_key="")
    assert len(advisory) > 20

    pdf_bytes = build_aqi_certificate(loc, telemetry, aqi_report, dispersion, advisory, "General Citizen")
    assert pdf_bytes.startswith(b"%PDF")
    assert b"IST" in _extract_pdf_text_bytes(pdf_bytes)


def test_pdf_international_country_timezone():
    loc = {
        "name": "Tokyo, Tokyo, Japan",
        "lat": 35.6762,
        "lon": 139.6503,
        "zone": "Admin Region: Tokyo",
        "is_land": True,
    }
    telemetry = {
        "timezone": "Asia/Tokyo",
        "timezone_abbr": "JST",
        "pollutants": {"pm2_5": 22.0, "pm10": 40.0, "no2": 18.0, "so2": 5.0, "o3": 30.0, "co": 250.0},
        "meteorology": {"temp_c": 18.0, "humidity_pct": 60.0, "wind_speed_kmh": 12.0, "wind_dir_deg": 90.0, "boundary_layer_m": 900.0},
    }
    aqi_report = compute_cpcb_aqi(telemetry["pollutants"])
    dispersion = analyze_dispersion(telemetry["meteorology"])
    advisory = generate_persona_advisory(loc["name"], aqi_report, dispersion, persona="General Citizen", api_key="")

    pdf_bytes = build_aqi_certificate(loc, telemetry, aqi_report, dispersion, advisory, "General Citizen")
    assert pdf_bytes.startswith(b"%PDF")
    assert b"JST" in _extract_pdf_text_bytes(pdf_bytes)
