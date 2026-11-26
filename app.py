"""AeroGuard Urban Air Quality Assistant - Interactive Streamlit Console."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.geocoder import DEFAULT_CITIES, resolve_location
from src.telemetry_ingestor import fetch_air_telemetry
from src.dispersion_analyzer import compute_cpcb_aqi, analyze_dispersion
from src.gemini_advisor import generate_persona_advisory
from src.pdf_reporter import build_aqi_certificate
from src.alert_dispatcher import dispatch_pdf_report


st.set_page_config(
    page_title="AeroGuard | Urban Air Quality AI Assistant",
    page_icon="🌬️",
    layout="wide",
)

# Support URL query parameter locking (?city=Visakhapatnam)
query_city = st.query_params.get("city", "Visakhapatnam")

st.title("🌬️ AeroGuard — Urban Air Quality & Public Health AI Assistant")
st.caption(
    "Real-time Copernicus CAMS Satellite Telemetry, CPCB AQI Analytics, Atmospheric Dispersion Modeling & Gemini Health Advisories"
)

with st.sidebar:
    st.header("📍 Urban Zone & Persona")
    preset_choice = st.selectbox(
        "Quick-Select Indian Metro",
        options=["Custom Search"] + list(DEFAULT_CITIES.keys()),
        index=(list(DEFAULT_CITIES.keys()).index(query_city) + 1) if query_city in DEFAULT_CITIES else 1,
    )

    custom_query = st.text_input(
        "Or Enter Any City / Neighborhood",
        value=query_city if preset_choice == "Custom Search" else preset_choice,
        help="Resolves street or city coordinates via OpenStreetMap Nominatim.",
    )

    persona = st.selectbox(
        "Advisory Persona",
        options=[
            "General Citizen",
            "Sensitive Group (Asthma / Elderly / Children)",
            "Outdoor Worker / Commuter",
            "Municipal / Urban Planner",
        ],
    )

    st.divider()
    st.subheader("🤖 Gen AI Configuration")
    user_gemini_key = st.text_input(
        "Gemini API Key (Optional)",
        type="password",
        help="Leave blank to use Streamlit Secrets or built-in deterministic advisory engine.",
    )

target_query = custom_query if preset_choice == "Custom Search" else preset_choice

try:
    with st.spinner(f"Resolving coordinates and ingesting live satellite telemetry for {target_query}..."):
        location = resolve_location(target_query)
        telemetry = fetch_air_telemetry(location["lat"], location["lon"])
        aqi_report = compute_cpcb_aqi(telemetry["pollutants"])
        dispersion = analyze_dispersion(telemetry["meteorology"])

        secret_gemini_key = ""
        if "gemini" in st.secrets:
            secret_gemini_key = st.secrets["gemini"].get("api_key", "")
        active_key = user_gemini_key or secret_gemini_key

        advisory_text = generate_persona_advisory(
            city_name=location["name"],
            aqi_report=aqi_report,
            dispersion=dispersion,
            persona=persona,
            api_key=active_key,
        )

    # Top Status Banner
    st.markdown(
        f"""
        <div style="padding:16px; border-radius:10px; background-color:{aqi_report['color']}22; border-left:6px solid {aqi_report['color']}; margin-bottom:16px;">
            <h3 style="margin:0; color:#111;">{location['name']}</h3>
            <p style="margin:4px 0 0 0; font-size:15px;">
                <strong>CPCB AQI: {aqi_report['aqi']} ({aqi_report['category']})</strong> &nbsp;|&nbsp;
                Dominant Pollutant: <strong>{aqi_report['dominant_pollutant']}</strong> &nbsp;|&nbsp;
                {aqi_report['health_impact']}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key Telemetry KPIs
    pol = telemetry["pollutants"]
    met = telemetry["meteorology"]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("CPCB AQI", f"{aqi_report['aqi']}", aqi_report["category"])
    c2.metric("PM2.5 (µg/m³)", f"{pol['pm2_5']:.1f}")
    c3.metric("PM10 (µg/m³)", f"{pol['pm10']:.1f}")
    c4.metric("NO₂ (µg/m³)", f"{pol['no2']:.1f}")
    c5.metric("Wind Speed", f"{met['wind_speed_kmh']:.1f} km/h")
    c6.metric("Mixing Layer", f"{met['boundary_layer_m']:.0f} m")

    # Main Two-Column Analytical View
    left_col, right_col = st.columns([1.15, 1])

    with left_col:
        st.subheader("📈 24-Hour Pollutant Trajectory")
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
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=20, b=10), legend_title_text="Pollutant")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("🌀 Atmospheric Dispersion & Ventilation")
        st.info(
            f"**{dispersion['dispersion_status']}** (Ventilation Index: `{dispersion['ventilation_index']}`)\n\n"
            f"{dispersion['dispersion_summary']}"
        )

    with right_col:
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
        st.download_button(
            label="⬇️ Download AQI Compliance Certificate (.PDF)",
            data=pdf_bytes,
            file_name=f"AeroGuard_AQI_{location['name'].split(',')[0].strip()}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        with st.expander("📧 Email Certificate via Encrypted TLS SMTP"):
            recipient = st.text_input("Recipient Email Address", placeholder="citizen@example.com")
            if st.button("Send PDF Report"):
                try:
                    smtp_user = st.secrets.get("gmail", {}).get("username", "")
                    smtp_pass = st.secrets.get("gmail", {}).get("app_password", "")
                    dispatch_pdf_report(recipient, location["name"], aqi_report["aqi"], pdf_bytes, smtp_user, smtp_pass)
                    st.success(f"Certificate sent successfully to {recipient}!")
                except Exception as mail_err:  # pylint: disable=broad-except
                    st.error(f"Email dispatch unavailable: {mail_err}")

except Exception as exc:  # pylint: disable=broad-except
    st.error(f"Unable to process air quality query: {exc}")
