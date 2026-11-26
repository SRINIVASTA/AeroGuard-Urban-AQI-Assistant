"""Enterprise FPDF2 Air Quality & Atmospheric Telemetry Report Builder with Stitched Map Tiles."""

import hashlib
import io
import math
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

import requests
from fpdf import FPDF
from PIL import Image, ImageDraw


def _sanitize_latin1(text: str) -> str:
    """Sanitizes text to Latin-1 for FPDF2 compatibility."""
    clean = text.replace("**", "").replace("•", "-").replace("µ", "u").replace("²", "2").replace("°", " deg")
    return clean.encode("latin-1", "replace").decode("latin-1")


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple:
    """Converts WGS84 lat/lon to Web Mercator slippy map tile indices and pixel offsets."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile_f = (lon_deg + 180.0) / 360.0 * n
    ytile_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    xtile = int(xtile_f)
    ytile = int(ytile_f)
    px = int((xtile_f - xtile) * 256)
    py = int((ytile_f - ytile) * 256)
    return xtile, ytile, px, py


def _fetch_spatial_map_image(lat: float, lon: float, zoom: int = 12) -> Optional[io.BytesIO]:
    """Stitches a 3x1 horizontal strip of Esri map tiles and draws a red target pin at (lat, lon)."""
    try:
        xtile, ytile, px, py = _deg2num(lat, lon, zoom)
        canvas = Image.new("RGB", (768, 256), (235, 240, 245))
        headers = {"User-Agent": "AeroGuard-Enterprise-GIS/1.0"}

        for idx, dx in enumerate((-1, 0, 1)):
            tx = xtile + dx
            tile_url = "".join(
                ("https://", "server.arcgisonline.", "com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/", f"{zoom}/{ytile}/{tx}")
            )
            resp = requests.get(tile_url, headers=headers, timeout=6)
            if resp.status_code == 200:
                tile_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                canvas.paste(tile_img, (idx * 256, 0))

        pin_x = 256 + px
        pin_y = py
        crop_left = max(0, min(768 - 720, pin_x - 360))
        crop_top = max(0, min(256 - 170, pin_y - 85))
        cropped = canvas.crop((crop_left, crop_top, crop_left + 720, crop_top + 170))

        rel_x = pin_x - crop_left
        rel_y = pin_y - crop_top
        draw = ImageDraw.Draw(cropped, "RGBA")
        draw.ellipse((rel_x - 28, rel_y - 28, rel_x + 28, rel_y + 28), fill=(220, 38, 38, 45), outline=(220, 38, 38, 180), width=2)
        draw.ellipse((rel_x - 6, rel_y - 6, rel_x + 6, rel_y + 6), fill=(220, 38, 38, 255), outline=(255, 255, 255, 255), width=2)

        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:  # pylint: disable=broad-except
        return None


def _draw_section_title(pdf: FPDF, title: str) -> None:
    """Renders bold uppercase navy section header matching enterprise report template."""
    pdf.ln(2.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(15, 44, 89)
    pdf.cell(0, 5.5, _sanitize_latin1(title), ln=True)
    pdf.set_text_color(25, 25, 25)


def _draw_table_row(pdf: FPDF, cells: tuple, widths: tuple, bold: bool = False, fill_rgb: Optional[tuple] = None) -> None:
    """Renders a bordered multi-column table row."""
    pdf.set_font("Helvetica", "B" if bold else "", 8)
    if fill_rgb:
        pdf.set_fill_color(*fill_rgb)
        fill = True
    else:
        fill = False
    pdf.set_draw_color(190, 200, 212)
    for text, width in zip(cells, widths):
        pdf.cell(width, 5.2, _sanitize_latin1(str(text)), border=1, fill=fill)
    pdf.ln()
def build_aqi_certificate(
    location: Dict[str, Any],
    telemetry: Dict[str, Any],
    aqi_report: Dict[str, Any],
    dispersion: Dict[str, str],
    advisory_text: str,
    persona: str,
) -> bytes:
    """Builds a single-page Enterprise Satellite Air Quality & Dispersion Report PDF."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(12, 10, 12)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    tz_name = telemetry.get("timezone", "Asia/Kolkata")
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:  # pylint: disable=broad-except
        local_tz = ZoneInfo("Asia/Kolkata")

    now_local = datetime.now(local_tz)
    tz_label = (
        "IST"
        if tz_name in ("Asia/Kolkata", "Asia/Calcutta")
        else (telemetry.get("timezone_abbr") or now_local.strftime("%Z"))
    )

    digest = hashlib.sha1(f"{location['lat']}:{location['lon']}:{now_local.isoformat()}".encode()).hexdigest()[:6].upper()
    ref_id = f"AER-{now_local.strftime('%Y%m%d')}-{digest}"
    stamp_str = f"{now_local.strftime('%d %b %Y, %I:%M %p')} {tz_label}"

    # Top Navy Enterprise Banner
    pdf.set_fill_color(15, 44, 89)
    pdf.rect(0, 0, 210, 22, style="F")

    # Vector Emblem Circle on Left
    pdf.set_fill_color(255, 255, 255)
    pdf.ellipse(13, 4.5, 13, 13, style="F")
    pdf.set_text_color(15, 44, 89)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_xy(13, 8.2)
    pdf.cell(13, 5, "AQ", align="C")

    # Header Title & Subtitle
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(30, 5)
    pdf.cell(0, 6, "AEROGUARD ENTERPRISE | SATELLITE AIR QUALITY REPORT", ln=True)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_x(30)
    pdf.cell(0, 5, "Copernicus CAMS & CPCB Atmospheric Telemetry, Dispersion & Health Assessment", ln=True)

    pdf.set_y(23)

    # 1. TARGET SITE LOCATION & REPORT METADATA
    _draw_section_title(pdf, "1. TARGET SITE LOCATION & REPORT METADATA")
    w_meta = (38, 55, 38, 55)
    _draw_table_row(pdf, ("Report Reference ID:", ref_id, "Assessment Date:", stamp_str), w_meta)
    _draw_table_row(
        pdf,
        ("Target Latitude:", f"{location['lat']:.6f} N", "Target Longitude:", f"{location['lon']:.6f} E"),
        w_meta,
    )
    _draw_table_row(
        pdf,
        ("Administrative Zone:", location["name"][:30], "Telemetry Model:", "Copernicus CAMS & GFS"),
        w_meta,
    )
    _draw_table_row(
        pdf,
        ("Resolved Locality:", location["name"][:30], "Target Persona:", persona[:28]),
        w_meta,
    )

    # OUTCOME HIGHLIGHT CALLOUT BOX
    pdf.ln(2.5)
    pdf.set_fill_color(244, 247, 251)
    pdf.set_draw_color(15, 44, 89)
    box_y = pdf.get_y()
    pdf.rect(12, box_y, 186, 14.5, style="DF")
    pdf.set_xy(14, box_y + 1.5)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(180, 40, 25)
    pol = telemetry["pollutants"]
    met = telemetry["meteorology"]
    outcome_head = (
        f"OUTCOME: {aqi_report['category'].upper()} AIR QUALITY (CPCB AQI {aqi_report['aqi']} | "
        f"Primary Driver: {aqi_report['dominant_pollutant']})"
    )
    pdf.cell(0, 4.5, _sanitize_latin1(outcome_head), ln=True)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(35, 35, 35)
    outcome_desc = (
        f"Satellite telemetry at {location['name']} records PM2.5 at {pol['pm2_5']:.1f} ug/m3 and NO2 at {pol['no2']:.1f} ug/m3 "
        f"with {met['boundary_layer_m']:.0f}m mixing layer ({dispersion['dispersion_status']})."
    )
    pdf.multi_cell(182, 4, _sanitize_latin1(outcome_desc))
    pdf.set_y(box_y + 15)

    # 2. SPATIAL SITE MAP
    _draw_section_title(pdf, "2. SPATIAL SITE MAP (RED TARGET PIN: SATELLITE OBSERVATION POINT)")
    map_buf = _fetch_spatial_map_image(location["lat"], location["lon"], zoom=12)
    map_y = pdf.get_y()
    if map_buf is not None:
        pdf.image(map_buf, x=12, y=map_y, w=186, h=42)
        pdf.set_draw_color(150, 165, 180)
        pdf.rect(12, map_y, 186, 42)
        pdf.set_y(map_y + 42.5)
    else:
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 8, f"[Spatial Grid Coordinates Locked: {location['lat']:.4f} N, {location['lon']:.4f} E]", border=1, ln=True)

    # 3. LIVE SATELLITE AIR QUALITY & DISPERSION METRICS
    _draw_section_title(pdf, "3. LIVE SATELLITE AIR QUALITY & DISPERSION METRICS")
    w_kpi = (68, 118)
    _draw_table_row(
        pdf,
        ("Overall CPCB Air Quality Index (AQI)", f"{aqi_report['aqi']} / 500 - {aqi_report['category']} ({aqi_report['health_impact']})"),
        w_kpi,
    )
    _draw_table_row(
        pdf,
        ("Fine Particulate Matter (PM2.5)", f"{pol['pm2_5']:.1f} ug/m3 (CPCB Sub-Index: {aqi_report['sub_indices'].get('PM2.5', 0)})"),
        w_kpi,
    )
    _draw_table_row(
        pdf,
        ("Coarse Particulate Matter (PM10)", f"{pol['pm10']:.1f} ug/m3 (CPCB Sub-Index: {aqi_report['sub_indices'].get('PM10', 0)})"),
        w_kpi,
    )
    _draw_table_row(
        pdf,
        ("Nitrogen Dioxide (NO2) & Ozone (O3)", f"NO2: {pol['no2']:.1f} ug/m3 | O3: {pol['o3']:.1f} ug/m3"),
        w_kpi,
    )
    _draw_table_row(
        pdf,
        ("Sulphur Dioxide (SO2) & Carbon Monoxide", f"SO2: {pol['so2']:.1f} ug/m3 | CO: {pol['co']:.1f} ug/m3"),
        w_kpi,
    )
    _draw_table_row(
        pdf,
        ("Atmospheric Ventilation & Mixing Layer", f"{dispersion['dispersion_status']} ({dispersion['ventilation_index']} | BLH: {met['boundary_layer_m']:.0f} m)"),
        w_kpi,
    )

    # 4. POLLUTANT SUB-INDEX & ATMOSPHERIC BOUNDARY LAYER PROFILE
    _draw_section_title(pdf, "4. POLLUTANT SUB-INDEX & ATMOSPHERIC BOUNDARY LAYER PROFILE")
    w_sub = (52, 34, 32, 68)
    _draw_table_row(
        pdf,
        ("Pollutant / Atmospheric Layer", "Measured Value", "CPCB Sub-Index", "Primary Urban Source"),
        w_sub,
        bold=True,
        fill_rgb=(235, 241, 248),
    )
    _draw_table_row(pdf, ("PM2.5 (Fine Aerosol)", f"{pol['pm2_5']:.1f} ug/m3", str(aqi_report["sub_indices"].get("PM2.5", 0)), "Combustion & Secondary Aerosols"), w_sub)
    _draw_table_row(pdf, ("PM10 (Respirable Dust)", f"{pol['pm10']:.1f} ug/m3", str(aqi_report["sub_indices"].get("PM10", 0)), "Road Dust & Construction"), w_sub)
    _draw_table_row(pdf, ("NO2 (Nitrogen Dioxide)", f"{pol['no2']:.1f} ug/m3", str(aqi_report["sub_indices"].get("NO2", 0)), "Vehicular & Industrial Exhaust"), w_sub)
    _draw_table_row(pdf, ("O3 (Tropospheric Ozone)", f"{pol['o3']:.1f} ug/m3", str(aqi_report["sub_indices"].get("O3", 0)), "Photochemical Smog Reaction"), w_sub)

    # 5. SATELLITE TELEMETRY PROVENANCE & CALIBRATION NOTES
    _draw_section_title(pdf, "5. SATELLITE TELEMETRY PROVENANCE & CALIBRATION NOTES")
    w_prov = (48, 38, 32, 68)
    _draw_table_row(
        pdf,
        ("Telemetry Parameter", "Assimilation Model", "Measured Value", "Atmospheric Role"),
        w_prov,
        bold=True,
        fill_rgb=(235, 241, 248),
    )
    _draw_table_row(pdf, ("PM2.5 / PM10 / NO2", "Copernicus CAMS", f"AQI {aqi_report['aqi']}", "Surface chemical transport grid"), w_prov)
    _draw_table_row(pdf, ("Boundary Layer Height", "ECMWF / GFS", f"{met['boundary_layer_m']:.0f} m", "Vertical pollutant dilution ceiling"), w_prov)
    _draw_table_row(pdf, ("Surface Wind Vector", "ECMWF / GFS", f"{met['wind_speed_kmh']:.1f} km/h", "Horizontal plume dispersion rate"), w_prov)

    # 6. PRELIMINARY SCREENING ADVISORY & DATA DISCLAIMER
    _draw_section_title(pdf, f"6. AI SCREENING ADVISORY ({persona.upper()}) & DISCLAIMER")
    pdf.set_font("Helvetica", "", 7.8)
    clean_adv = _sanitize_latin1(advisory_text).replace("\n", " ")
    pdf.multi_cell(186, 4.2, clean_adv)

    # Bottom Footer Bar (Strictly Single Page)
    pdf.set_y(284)
    pdf.set_draw_color(180, 190, 205)
    pdf.line(12, 283, 198, 283)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(100, 110, 120)
    pdf.cell(
        0,
        4,
        _sanitize_latin1(
            f"AeroGuard Enterprise | Powered by Tanakala AI Solutions | Generated on {stamp_str} | Page 1"
        ),
        align="C",
    )

    return bytes(pdf.output())
