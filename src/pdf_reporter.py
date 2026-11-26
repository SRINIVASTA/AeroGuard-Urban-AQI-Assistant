"""FPDF2 Automated Air Quality Compliance & Health Advisory Certificate Builder."""

from datetime import datetime, timezone
from typing import Dict, Any
from fpdf import FPDF


def _sanitize_latin1(text: str) -> str:
    """Strips non-Latin-1 characters so FPDF2 renders cleanly without encoding errors."""
    clean = text.replace("**", "").replace("•", "-")
    return clean.encode("latin-1", "replace").decode("latin-1")


def build_aqi_certificate(
    location: Dict[str, Any],
    telemetry: Dict[str, Any],
    aqi_report: Dict[str, Any],
    dispersion: Dict[str, str],
    advisory_text: str,
    persona: str,
) -> bytes:
    """Generates a single-page technical Air Quality Certificate as raw PDF bytes."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header Banner
    pdf.set_fill_color(15, 44, 89)
    pdf.rect(0, 0, 210, 32, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(12, 9)
    pdf.cell(0, 8, "AEROGUARD URBAN AIR QUALITY INTELLIGENCE CERTIFICATE", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(12)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Copernicus CAMS & CPCB Telemetry Audit | Generated: {stamp}", ln=True)

    # Site Metadata
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(12, 38)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "1. MONITORED URBAN ZONE", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _sanitize_latin1(f"Location: {location['name']}"), ln=True)
    pdf.cell(0, 6, f"Coordinates: {location['lat']:.4f} N, {location['lon']:.4f} E | Zone: {location['zone']}", ln=True)

    # AQI Summary Box
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "2. CPCB AIR QUALITY INDEX & DOMINANT POLLUTANT", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        6,
        f"Overall CPCB AQI: {aqi_report['aqi']} ({aqi_report['category']}) | Primary Driver: {aqi_report['dominant_pollutant']}",
        ln=True,
    )
    pdf.multi_cell(0, 5, _sanitize_latin1(f"Health Impact: {aqi_report['health_impact']}"))

    # Pollutant Breakdown Table
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "3. SURFACE CONCENTRATIONS & METEOROLOGY", ln=True)
    pol = telemetry["pollutants"]
    met = telemetry["meteorology"]
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"PM2.5: {pol['pm2_5']:.1f} ug/m3  |  PM10: {pol['pm10']:.1f} ug/m3  |  NO2: {pol['no2']:.1f} ug/m3", ln=True)
    pdf.cell(0, 6, f"SO2: {pol['so2']:.1f} ug/m3    |  O3: {pol['o3']:.1f} ug/m3    |  CO: {pol['co']:.1f} ug/m3", ln=True)
    pdf.cell(
        0,
        6,
        f"Temp: {met['temp_c']:.1f} C | Humidity: {met['humidity_pct']:.0f}% | Wind: {met['wind_speed_kmh']:.1f} km/h | Mixing Layer: {met['boundary_layer_m']:.0f} m",
        ln=True,
    )
    pdf.cell(0, 6, _sanitize_latin1(f"Dispersion Status: {dispersion['dispersion_status']} ({dispersion['ventilation_index']})"), ln=True)

    # AI Persona Advisory
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _sanitize_latin1(f"4. AI ADVISORY BRIEF ({persona.upper()})"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, _sanitize_latin1(advisory_text))

    # Footer Disclaimer (Strictly Single-Page Fit)
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-24)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        4,
        "Disclaimer: Screening report derived from Copernicus CAMS & Open-Meteo satellite assimilation models. "
        "Verify critical regulatory decisions with local CPCB/SPCB ground monitoring stations.",
    )

    return bytes(pdf.output())
