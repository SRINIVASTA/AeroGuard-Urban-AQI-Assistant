"""AeroGuard Urban Air Quality Assistant - 100% Dynamic Global Console."""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.geocoder import resolve_location, resolve_coordinates
from src.telemetry_ingestor import fetch_air_telemetry
from src.dispersion_analyzer import compute_cpcb_aqi, analyze_dispersion
from src.gemini_advisor import generate_persona_advisory
from src.pdf_reporter import build_aqi_certificate
from src.alert_dispatcher import dispatch_pdf_report


st.set_page_config(
    page_title="AeroGuard | Global Air Quality AI Assistant",
    page_icon="🌬️",
    layout="wide",
)


def _get_secret_safe(section: str, key: str) -> str:
    """Safely reads Streamlit secrets without crashing when secrets.toml is absent."""
    try:
        return st.secrets[section][key]
    except Exception:  # pylint: disable=broad-except
        return os.getenv(f"{section.upper()}_{key.upper()}", "")


st.title("🌬️ AeroGuard — Live Global Urban Air Quality & Health AI Assistant")
st.caption(
    "100% Dynamic Worldwide Copernicus CAMS Satellite Telemetry, AQI Analytics, Atmospheric Dispersion & AI Health Advisories"
)

with st.sidebar:
    st.header("🌍 Live Global Target")
    search_mode = st.radio(
        "Select Input Type",
        options=["Type City / Place Name", "Type Latitude & Longitude"],
    )

    if search_mode == "Type City / Place Name":
        city_input = st.text_input(
            "City / Town / Area Worldwide",
            value=st.query_params.get("city", "Visakhapatnam"),
            placeholder="Type any place on Earth (e.g., Gajuwaka, Tokyo, Paris, Cairo)",
        )
    else:
        lat_input = st.number_input(
            "Latitude (-90.0 to 90.0)",
            min_value=-90.0,
            max_value=90.0,
            value=float(st.query_params.get("lat", 17.6868)),
            format="%.4f",
        )
        lon_input = st.number_input(
            "Longitude (-180.0 to 180.0)",
            min_value=-180.0,
            max_value=180.0,
            value=float(st.query_params.get("lon", 83.2185)),
            format="%.4f",
        )

    st.divider()
    persona = st.selectbox(
        "Advisory Persona",
        options=[
            "General Citizen",
            "Sensitive Group (Asthma / Elderly / Children)",
            "Outdoor Worker / Commuter",
            "Municipal / Urban Planner",
        ],
    )

    user_gemini_key = st.text_input(
        "Gemini API Key (Optional)",
        type="password",
        help="Optional: Leave blank to use the built-in deterministic advisory engine.",
    )

try:
    with st.spinner("Resolving live coordinates and ingesting real-time satellite telemetry..."):
        if search_mode == "Type City / Place Name":
            location = resolve_location(city_input)
        else:
            location = resolve_coordinates(lat_input, lon_input)

        telemetry = fetch_air_telemetry(location["lat"], location["lon"])
        aqi_report = compute_cpcb_aqi(telemetry["pollutants"])
        dispersion = analyze_dispersion(telemetry["meteorology"])

        active_key = user_gemini_key or _get_secret_safe("gemini", "api_key")

        advisory_text = generate_persona_advisory(
            city_name=location["name"],
            aqi_report=aqi_report,
            dispersion=dispersion,
            persona=persona,
            api_key=active_key,
        )

    # Top Status Banner with Live Resolved Place & Exact Coordinates
    st.markdown(
        f"""
        <div style="padding:16px; border-radius:10px; background-color:{aqi_report['color']}22; border-left:6px solid {aqi_report['color']}; margin-bottom:16px;">
            <h3 style="margin:0; color:#111;">{location['name']}</h3>
            <p style="margin:4px 0; font-size:13px; color:#333;">
                📍 <strong>Live Coordinates:</strong> {location['lat']:.4f}° N, {location['lon']:.4f}° E &nbsp;|&nbsp;
                <strong>Metadata:</strong> {location['zone']}
            </p>
            <p style="margin:4px 0 0 0; font-size:15px;">
                <strong>Live AQI: {aqi_report['aqi']} ({aqi_report['category']})</strong> &nbsp;|&nbsp;
                Dominant Pollutant: <strong>{aqi_report['dominant_pollutant']}</strong> &nbsp;|&nbsp;
                {aqi_report['health_impact']}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Live Telemetry KPIs
    pol = telemetry["pollutants"]
    met = telemetry["meteorology"]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Live AQI", f"{aqi_report['aqi']}", aqi_report["category"])
    c2.metric("PM2.5 (µg/m³)", f"{pol['pm2_5']:.1f}")
    c3.metric("PM10 (µg/m³)", f"{pol['pm10']:.1f}")
    c4.metric("NO₂ (µg/m³)", f"{pol['no2']:.1f}")
    c5.metric("Wind Speed", f"{met['wind_speed_kmh']:.1f} km/h")
    c6.metric("Mixing Layer", f"{met['boundary_layer_m']:.0f} m")

    left_col, right_col = st.columns([1.15, 1])

    with left_col:
        st.subheader("🗺️ Live Satellite Telemetry & Geospatial Grid Map")
        map_fig = go.Figure(
            go.Scattermapbox(
                lat=[location["lat"]],
                lon=[location["lon"]],
                mode="markers+text",
                marker=go.scattermapbox.Marker(
                    size=26,
                    color=aqi_report["color"],
                    opacity=0.85,
                ),
                text=[f"{location['name']} | AQI: {aqi_report['aqi']} ({aqi_report['category']})"],
                textposition="top center",
                hovertemplate=(
                    f"<b>{location['name']}</b><br>"
                    f"Lat: {location['lat']:.4f}, Lon: {location['lon']:.4f}<br>"
                    f"AQI: {aqi_report['aqi']} ({aqi_report['category']})<br>"
                    f"PM2.5: {pol['pm2_5']:.1f} µg/m³ | PM10: {pol['pm10']:.1f} µg/m³<extra></extra>"
                ),
            )
        )
        map_fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
                center=dict(lat=location["lat"], lon=location["lon"]),
                zoom=10,
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=330,
        )
        st.plotly_chart(map_fig, use_container_width=True)

        st.subheader("📈 Live 24-Hour Pollutant Trajectory")
        hourly = telemetry.get("hourly", {})
        if hourly and "time" in hourly:
            df_hourly = pd.DataFrame(
                {
                    "Time": pd.to_datetime(hourly["time"]),
                    "PM2.5 (µg/m³)": hourly.get("pm2_5", []),
                    "PM10 (µg/m³)": hourly.get("pm10", []),
                    "NO₂ (µg/m³)": hourly.get("nitrogen_dioxide", []),
                }
            )
            fig = px.line(
                df_hourly,
                x="Time",
                y=["PM2.5 (µg/m³)", "PM10 (µg/m³)", "NO₂ (µg/m³)"],
                markers=True,
            )
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), legend_title_text="Pollutant")
            st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.subheader("🌀 Atmospheric Dispersion & Ventilation")
        st.info(
            f"**{dispersion['dispersion_status']}** (Ventilation Index: `{dispersion['ventilation_index']}`)\n\n"
            f"{dispersion['dispersion_summary']}"
        )

        st.subheader(f"🧠 AI Health & Action Advisory ({persona})")
        st.success(advisory_text)

        st.subheader("📄 Export & Dispatch Official Certificate")
        pdf_bytes = build_aqi_certificate(
            location=location,
            telemetry=telemetry,
            aqi_report=aqi_report,
            dispersion=dispersion,
            advisory_text=advisory_text,
            persona=persona,
        )
        safe_city_slug = location["name"].split(",").strip().replace(" ", "_")
        st.download_button(
            label="⬇️ Download AQI Compliance Certificate (.PDF)",
            data=pdf_bytes,
            file_name=f"AeroGuard_AQI_{safe_city_slug}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        with st.expander("📧 Email Certificate via Encrypted TLS SMTP"):
            recipient = st.text_input("Recipient Email Address", placeholder="citizen@example.com")
            if st.button("Send PDF Report"):
                try:
                    smtp_user = _get_secret_safe("gmail", "username")
                    smtp_pass = _get_secret_safe("gmail", "app_password")
                    dispatch_pdf_report(recipient, location["name"], aqi_report["aqi"], pdf_bytes, smtp_user, smtp_pass)
                    st.success(f"Certificate sent successfully to {recipient}!")
                except Exception as mail_err:  # pylint: disable=broad-except
                    st.error(f"Email dispatch unavailable: {mail_err}")

except Exception as exc:  # pylint: disable=broad-except
    st.error(f"Unable to process air quality query: {exc}")
