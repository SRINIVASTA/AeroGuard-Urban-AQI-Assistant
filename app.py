"""AeroGuard Urban Air Quality Assistant - True Click-Anywhere Global Geospatial Console."""

import os
import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

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


def _clear_map_pin() -> None:
    """Clears active map click override when user edits sidebar inputs."""
    st.session_state["clicked_coords"] = None


if "clicked_coords" not in st.session_state:
    st.session_state["clicked_coords"] = None

st.title("🌬️ AeroGuard — Live Global Urban Air Quality & Health AI Assistant")
st.caption(
    "Click Anywhere on the Global Map, Search Any City, or Enter Exact Coordinates for Live Copernicus CAMS Telemetry & AI Advisories"
)

with st.sidebar:
    st.header("🌍 Live Global Target")
    search_mode = st.radio(
        "Select Input Type",
        options=["Type City / Place Name", "Type Latitude & Longitude"],
        on_change=_clear_map_pin,
    )

    if search_mode == "Type City / Place Name":
        city_input = st.text_input(
            "City / Town / Area Worldwide",
            value=st.query_params.get("city", "Visakhapatnam"),
            placeholder="Type any place on Earth (e.g., Gajuwaka, Tokyo, Paris, Cairo)",
            on_change=_clear_map_pin,
        )
    else:
        lat_input = st.number_input(
            "Latitude (-90.0 to 90.0)",
            min_value=-90.0,
            max_value=90.0,
            value=float(st.query_params.get("lat", 17.6868)),
            format="%.4f",
            key="lat_box",
            on_change=_clear_map_pin,
        )
        lon_input = st.number_input(
            "Longitude (-180.0 to 180.0)",
            min_value=-180.0,
            max_value=180.0,
            value=float(st.query_params.get("lon", 83.2185)),
            format="%.4f",
            key="lon_box",
            on_change=_clear_map_pin,
        )

    if st.session_state["clicked_coords"] is not None:
        c_lat, c_lon = st.session_state["clicked_coords"]
        st.info(f"📌 Map Pin Active: `{c_lat:.5f}°, {c_lon:.5f}°`")
        if st.button("Reset to Sidebar Search", use_container_width=True):
            _clear_map_pin()
            st.rerun()

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
        if st.session_state["clicked_coords"] is not None:
            sel_lat, sel_lon = st.session_state["clicked_coords"]
            location = resolve_coordinates(sel_lat, sel_lon)
        elif search_mode == "Type City / Place Name":
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

    # Top Status Banner (High Contrast for Dark & Light Themes)
    st.markdown(
        f"""
        <div style="padding:16px; border-radius:10px; background-color:#1E2530; border-left:6px solid {aqi_report['color']}; margin-bottom:16px;">
            <h3 style="margin:0; color:#FAFAFA;">{location['name']}</h3>
            <p style="margin:4px 0; font-size:13px; color:#D1D5DB;">
                📍 <strong>Live Coordinates:</strong> {location['lat']:.5f}° N, {location['lon']:.5f}° E &nbsp;|&nbsp;
                <strong>Metadata:</strong> {location['zone']} &nbsp;|&nbsp;
                <strong>Grid:</strong> Copernicus CAMS (~11 km cell)
            </p>
            <p style="margin:4px 0 0 0; font-size:15px; color:#FAFAFA;">
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
        st.subheader("🗺️ Interactive Geospatial Map (Click Anywhere to Sample Point)")
        m = folium.Map(location=[location["lat"], location["lon"]], zoom_start=11, control_scale=True)
        folium.Circle(
            location=[location["lat"], location["lon"]],
            radius=5500,
            color=aqi_report["color"],
            fill=True,
            fill_opacity=0.15,
            tooltip="Copernicus CAMS Satellite Grid Footprint (~11 km diameter)",
        ).add_to(m)
        folium.Marker(
            location=[location["lat"], location["lon"]],
            popup=f"<b>{location['name']}</b><br>AQI: {aqi_report['aqi']} ({aqi_report['category']})<br>Lat: {location['lat']:.5f}, Lon: {location['lon']:.5f}",
            tooltip=f"{location['name']} | AQI: {aqi_report['aqi']}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)
        folium.LatLngPopup().add_to(m)

        map_state = st_folium(m, height=330, use_container_width=True, key="aeroguard_folium_map")
        if map_state and map_state.get("last_clicked"):
            clicked_lat = float(map_state["last_clicked"]["lat"])
            clicked_lon = float(map_state["last_clicked"]["lng"])
            if abs(clicked_lat - location["lat"]) > 1e-4 or abs(clicked_lon - location["lon"]) > 1e-4:
                st.session_state["clicked_coords"] = (clicked_lat, clicked_lon)
                st.rerun()

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
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=20, b=10), legend_title_text="Pollutant")
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
        city_prefix = next(iter(location["name"].split(","))).strip().replace(" ", "_")

        with st.container(border=True):
            recipient = st.text_input(
                "Recipient Email Address (for TLS SMTP Dispatch)",
                placeholder="citizen@example.com",
            )
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"AeroGuard_AQI_{city_prefix}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with btn_col2:
                send_clicked = st.button("📧 Email PDF Report", use_container_width=True)

            if send_clicked:
                if not recipient.strip():
                    st.warning("Please enter a valid recipient email address above.")
                else:
                    try:
                        smtp_user = _get_secret_safe("gmail", "username")
                        smtp_pass = _get_secret_safe("gmail", "app_password")
                        dispatch_pdf_report(recipient.strip(), location["name"], aqi_report["aqi"], pdf_bytes, smtp_user, smtp_pass)
                        st.success(f"Certificate dispatched to {recipient.strip()}!")
                    except Exception as mail_err:  # pylint: disable=broad-except
                        st.error(f"Email dispatch unavailable: {mail_err}")

except Exception as exc:  # pylint: disable=broad-except
    st.error(f"Unable to process air quality query: {exc}")
