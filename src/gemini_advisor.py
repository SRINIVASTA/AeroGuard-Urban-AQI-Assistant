"""Gen AI Advisory Engine using Google Gemini with deterministic offline fallback."""

import os
from typing import Dict, Any, Optional


def generate_persona_advisory(
    city_name: str,
    aqi_report: Dict[str, Any],
    dispersion: Dict[str, str],
    persona: str = "General Citizen",
    api_key: Optional[str] = None,
) -> str:
    """Generates tailored health & operational guidance using Gemini or rule-based engine."""
    resolved_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    fallback_reason = "No API key provided"

    if resolved_key:
        try:
            from google import genai  # pylint: disable=import-outside-toplevel

            client = genai.Client(api_key=resolved_key)
            prompt = (
                f"You are AeroGuard, an Urban Air Quality & Public Health AI Assistant.\n"
                f"City: {city_name}\n"
                f"CPCB AQI: {aqi_report['aqi']} ({aqi_report['category']})\n"
                f"Dominant Pollutant: {aqi_report['dominant_pollutant']}\n"
                f"Atmospheric Dispersion: {dispersion['dispersion_status']} - {dispersion['dispersion_summary']}\n"
                f"Target Persona: {persona}\n\n"
                f"Provide a crisp, actionable 3-bullet advisory tailored strictly to a '{persona}'. "
                f"Include specific timing, protective gear/filtration, and exposure thresholds. Keep under 120 words."
            )

            last_err = ""
            for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if response and response.text:
                        return f"{response.text.strip()}\n\n*✨ Engine: Live Google Gemini ({model_name})*"
                except Exception as model_err:  # pylint: disable=broad-except
                    last_err = str(model_err)

            fallback_reason = last_err[:120] if last_err else "Empty response from Gemini"
        except ImportError:
            fallback_reason = "google-genai package not installed in requirements.txt"
        except Exception as err:  # pylint: disable=broad-except
            fallback_reason = str(err)[:120]

    # Deterministic structured fallback when no API key is configured or API call fails
    aqi_val = aqi_report["aqi"]
    dom = aqi_report["dominant_pollutant"]
    persona_tips = {
        "General Citizen": (
            f"- **Outdoor Timing:** Plan walks or errands when {dom} levels dip; {aqi_report['general_advisory']}\n"
            f"- **Ventilation:** {dispersion['dispersion_summary']} Adjust window ventilation accordingly.\n"
            f"- **Protection:** Keep a certified N95/KN95 mask accessible if AQI exceeds 150."
        ),
        "Sensitive Group (Asthma / Elderly / Children)": (
            f"- **Exposure Limit:** Current AQI is **{aqi_val} ({aqi_report['category']})** driven by **{dom}**. Limit strenuous outdoor exertion.\n"
            f"- **Indoor Air:** Keep rescue inhalers/medications handy and use HEPA filtration indoors.\n"
            f"- **Masking:** Wear a well-fitted N95 mask for any unavoidable outdoor transit."
        ),
        "Outdoor Worker / Commuter": (
            f"- **Shift Protection:** Primary exposure hazard is **{dom}** at AQI **{aqi_val}**.\n"
            f"- **PPE Guidance:** Use an N95 respirator during peak traffic hours and hydrate frequently.\n"
            f"- **Micro-Breaks:** Take scheduled breaks in enclosed or vegetated zones away from arterial roads."
        ),
        "Municipal / Urban Planner": (
            f"- **Hotspot Control:** Dominant pollutant **{dom}** under **{dispersion['dispersion_status']}**.\n"
            f"- **Mitigation Action:** Deploy anti-smog water sprinklers along high-traffic corridors and audit construction dust.\n"
            f"- **Public Alerting:** Issue ward-level advisory notices if AQI trends above 200."
        ),
    }
    base_tip = persona_tips.get(persona, persona_tips["General Citizen"])
    return f"{base_tip}\n\n*⚙️ Engine: Deterministic Rule Engine ({fallback_reason})*"
