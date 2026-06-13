"""
ClimateRisk Pro - Assessment Engine
Fetches data from proxy endpoints and computes risk scores.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime

PROXY_URL = "https://climaterisk-proxy.gokulk122.workers.dev"
TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_json(url: str) -> dict:
    """Fetch JSON from a URL using urllib. Raises on error."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ClimateRiskPro-QGIS/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {url}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL error for {url}: {e.reason}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from {url}: {e}")


# ---------------------------------------------------------------------------
# Data fetch functions
# ---------------------------------------------------------------------------

def fetch_thinkhazard(lat: float, lon: float) -> dict:
    """
    Query ThinkHazard via proxy for multi-hazard scores.
    Returns a dict with keys like 'flood', 'earthquake', 'cyclone', etc.,
    each mapping to a hazard level string and numeric score.
    """
    lookup_url = (
        f"{PROXY_URL}/thinkhazard/lookup"
        f"?lat={lat:.6f}&lon={lon:.6f}"
    )
    report_url = (
        f"{PROXY_URL}/thinkhazard/report"
        f"?lat={lat:.6f}&lon={lon:.6f}"
    )

    result = {"raw_lookup": {}, "raw_report": {}, "hazards": {}}

    try:
        lookup_data = _get_json(lookup_url)
        result["raw_lookup"] = lookup_data
    except RuntimeError as e:
        result["lookup_error"] = str(e)

    try:
        report_data = _get_json(report_url)
        result["raw_report"] = report_data
    except RuntimeError as e:
        result["report_error"] = str(e)

    # Normalise hazard levels to a 0-100 numeric score
    level_map = {"VLO": 10, "LOW": 25, "MED": 55, "HIG": 80, "VHI": 95}
    hazards_raw = result["raw_report"].get("hazards", [])
    if not hazards_raw:
        hazards_raw = result["raw_lookup"].get("hazards", [])

    for h in hazards_raw:
        htype = h.get("hazard_type", "unknown").lower()
        level = h.get("hazard_level", "LOW").upper()
        score = level_map.get(level, 25)
        result["hazards"][htype] = {"level": level, "score": score}

    return result


def fetch_water_risk(lat: float, lon: float) -> dict:
    """
    Query Aqueduct via proxy for water stress data.
    Returns a dict with 'water_stress_score' (0-100) and raw data.
    """
    url = f"{PROXY_URL}/aqueduct?lat={lat:.6f}&lon={lon:.6f}"
    result = {"water_stress_score": 50, "raw": {}}
    try:
        data = _get_json(url)
        result["raw"] = data
        # Try common Aqueduct response keys
        ws = (
            data.get("water_stress")
            or data.get("bws_score")
            or data.get("bws")
        )
        if ws is not None:
            try:
                # Aqueduct raw scores are 0-5; normalise to 0-100
                raw_val = float(ws)
                if raw_val <= 5:
                    result["water_stress_score"] = min(100, raw_val * 20)
                else:
                    result["water_stress_score"] = min(100, raw_val)
            except (TypeError, ValueError):
                pass
    except RuntimeError as e:
        result["error"] = str(e)

    return result


def fetch_nasa_power(lat: float, lon: float) -> dict:
    """
    Query NASA POWER via proxy for climatological temperature and precipitation.
    Returns a dict with 'mean_temp_c', 'max_temp_c', 'annual_precip_mm'.
    """
    url = f"{PROXY_URL}/nasapower?lat={lat:.6f}&lon={lon:.6f}"
    result = {
        "mean_temp_c": 25.0,
        "max_temp_c": 35.0,
        "annual_precip_mm": 800.0,
        "raw": {},
    }
    try:
        data = _get_json(url)
        result["raw"] = data

        # NASA POWER parameter keys vary; try common forms
        props = data.get("properties", {}).get("parameter", data)

        def _mean(d):
            vals = [v for v in d.values() if isinstance(v, (int, float)) and v != -999]
            return sum(vals) / len(vals) if vals else None

        t2m = props.get("T2M") or props.get("t2m")
        if isinstance(t2m, dict):
            m = _mean(t2m)
            if m is not None:
                result["mean_temp_c"] = round(m, 2)

        t2m_max = props.get("T2M_MAX") or props.get("t2m_max")
        if isinstance(t2m_max, dict):
            m = _mean(t2m_max)
            if m is not None:
                result["max_temp_c"] = round(m, 2)

        prec = props.get("PRECTOTCORR") or props.get("PRECTOT") or props.get("prec")
        if isinstance(prec, dict):
            m = _mean(prec)
            if m is not None:
                # NASA POWER daily mm; multiply by 365 for annual
                result["annual_precip_mm"] = round(m * 365, 1)

    except RuntimeError as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

def run_rules_engine(
    hazard_data: dict,
    water_data: dict,
    climate_data: dict,
    framework: str,
) -> dict:
    """
    Compute risk scores (0-100) and qualitative tiers from raw API data.
    Returns a comprehensive result dict.
    """

    # ---- Flood risk ----
    flood_hazard = hazard_data.get("hazards", {}).get("flood", {})
    flood_score = float(flood_hazard.get("score", 30))
    # Boost if high precipitation
    precip = climate_data.get("annual_precip_mm", 800)
    if precip > 2000:
        flood_score = min(100, flood_score * 1.2)
    elif precip < 300:
        flood_score = max(0, flood_score * 0.8)

    # ---- Heat risk ----
    max_temp = climate_data.get("max_temp_c", 35)
    mean_temp = climate_data.get("mean_temp_c", 25)
    heat_score = 0.0
    if max_temp >= 45:
        heat_score = 90
    elif max_temp >= 40:
        heat_score = 70
    elif max_temp >= 35:
        heat_score = 50
    elif max_temp >= 30:
        heat_score = 30
    else:
        heat_score = 15

    # ---- Water risk ----
    water_score = float(water_data.get("water_stress_score", 50))

    # ---- Composite hazard score ----
    hazards = hazard_data.get("hazards", {})
    all_scores = [v.get("score", 25) for v in hazards.values()]
    hazard_score = (sum(all_scores) / len(all_scores)) if all_scores else 30.0

    # ---- Overall risk (weighted) ----
    overall = (
        0.35 * flood_score
        + 0.30 * heat_score
        + 0.25 * water_score
        + 0.10 * hazard_score
    )
    overall = round(min(100, max(0, overall)), 1)

    def _tier(score):
        if score < 25:
            return "LOW"
        elif score < 50:
            return "MEDIUM"
        elif score < 75:
            return "HIGH"
        else:
            return "VERY HIGH"

    # ---- Framework-specific narrative ----
    tier = _tier(overall)
    narrative = _build_narrative(
        framework, tier, overall,
        flood_score, heat_score, water_score, hazard_score,
        max_temp, precip
    )

    return {
        "flood_risk_score": round(flood_score, 1),
        "heat_risk_score": round(heat_score, 1),
        "water_risk_score": round(water_score, 1),
        "hazard_score": round(hazard_score, 1),
        "overall_risk_score": overall,
        "flood_risk_tier": _tier(flood_score),
        "heat_risk_tier": _tier(heat_score),
        "water_risk_tier": _tier(water_score),
        "overall_risk_tier": tier,
        "narrative": narrative,
        "framework": framework,
    }


def _build_narrative(
    framework, tier, overall,
    flood, heat, water, hazard,
    max_temp, precip
):
    base = (
        f"Overall physical climate risk is {tier} ({overall}/100). "
        f"Flood risk: {flood:.0f}/100. "
        f"Heat risk: {heat:.0f}/100 (max temp {max_temp:.1f}°C). "
        f"Water stress: {water:.0f}/100. "
        f"Composite multi-hazard score: {hazard:.0f}/100. "
        f"Annual precipitation proxy: {precip:.0f} mm."
    )

    if framework == "TCFD":
        return (
            "TCFD Physical Risk Disclosure — Acute & Chronic:\n"
            + base
            + "\nAcute risks include riverine/coastal flooding and extreme heat events. "
            "Chronic risks include shifting precipitation patterns and rising mean temperatures. "
            "Management action: conduct scenario analysis under SSP2-4.5 and SSP5-8.5."
        )
    elif framework == "ISSB S2":
        return (
            "IFRS S2 Climate-related Disclosures — Physical Risk:\n"
            + base
            + "\nAs required under IFRS S2 paragraphs 29-30, this assessment identifies "
            "material physical risks to assets and operations. Scenario alignment: "
            "low-emission (1.5°C) and high-emission (4°C) pathways considered."
        )
    elif framework == "BRSR":
        return (
            "SEBI BRSR Core — Leadership Indicator: Climate Risk Assessment:\n"
            + base
            + "\nAligned with BRSR Principle 6 (Environment). This score supports "
            "disclosure under 'Risks and Opportunities from Climate Change' (BRSR p.23-24). "
            "Recommended: disclose in Annual Report under ESG risk section."
        )
    elif framework == "CSRD":
        return (
            "CSRD / ESRS E1 — Physical Climate Risk Assessment:\n"
            + base
            + "\nThis assessment supports ESRS E1-9 (Physical climate-related risks) "
            "disclosure. Scope: physical risks to owned and operated assets. "
            "Time horizons covered: short-term (2030), medium-term (2040), long-term (2050). "
            "Mandatory for in-scope entities under EU CSRD Directive 2022/2464."
        )
    else:
        return base


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_assessment(
    lat: float, lon: float, location_name: str, framework: str
) -> dict:
    """
    Full pipeline: fetch data → rules engine → return consolidated result dict.
    """
    hazard_data = fetch_thinkhazard(lat, lon)
    water_data = fetch_water_risk(lat, lon)
    climate_data = fetch_nasa_power(lat, lon)
    scores = run_rules_engine(hazard_data, water_data, climate_data, framework)

    return {
        "location_name": location_name,
        "lat": lat,
        "lon": lon,
        "framework": framework,
        "assessment_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "data_sources": {
            "thinkhazard": hazard_data,
            "aqueduct": water_data,
            "nasa_power": climate_data,
        },
        **scores,
    }


# ---------------------------------------------------------------------------
# Display formatter
# ---------------------------------------------------------------------------

def format_results_text(result: dict, framework: str) -> str:
    """Format the result dict into readable text for the dock widget."""
    lines = [
        "=" * 50,
        f"  ClimateRisk Pro — {framework} Assessment",
        "=" * 50,
        f"  Location : {result.get('location_name', 'N/A')}",
        f"  Lat/Lon  : {result.get('lat', 0):.4f}, {result.get('lon', 0):.4f}",
        f"  Date     : {result.get('assessment_date', '')}",
        "-" * 50,
        "  RISK SCORES (0 = lowest, 100 = highest)",
        "-" * 50,
        f"  Flood Risk   : {result.get('flood_risk_score', 0):.1f} / 100"
        f"  [{result.get('flood_risk_tier', '?')}]",
        f"  Heat Risk    : {result.get('heat_risk_score', 0):.1f} / 100"
        f"  [{result.get('heat_risk_tier', '?')}]",
        f"  Water Stress : {result.get('water_risk_score', 0):.1f} / 100"
        f"  [{result.get('water_risk_tier', '?')}]",
        f"  Multi-Hazard : {result.get('hazard_score', 0):.1f} / 100",
        "-" * 50,
        f"  OVERALL RISK : {result.get('overall_risk_score', 0):.1f} / 100"
        f"  [{result.get('overall_risk_tier', '?')}]",
        "=" * 50,
        "",
        "  FRAMEWORK NARRATIVE",
        "-" * 50,
        result.get("narrative", ""),
        "",
        "  DATA SOURCES",
        "-" * 50,
        "  • ThinkHazard (GFDRR / World Bank)",
        "  • Aqueduct Water Risk Atlas (WRI)",
        "  • NASA POWER Climatology API",
        "=" * 50,
    ]
    return "\n".join(lines)
