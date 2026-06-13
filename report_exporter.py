"""
ClimateRisk Pro - Report Exporter
Generates plain-text disclosure reports aligned to TCFD / ISSB S2 / BRSR / CSRD.
"""

import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox


# ---------------------------------------------------------------------------
# Report builders per framework
# ---------------------------------------------------------------------------

def _header(result: dict, framework: str) -> str:
    lines = [
        "=" * 70,
        f"  CLIMATERISK PRO — {framework} PHYSICAL CLIMATE RISK REPORT",
        "=" * 70,
        f"  Generated : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"  Plugin    : ClimateRisk Pro v1.0.0",
        f"  Author    : Gokul Krishna T.B. <tbgokulkrishna@gmail.com>",
        "-" * 70,
        f"  Location  : {result.get('location_name', 'N/A')}",
        f"  Latitude  : {result.get('lat', 0):.6f}°",
        f"  Longitude : {result.get('lon', 0):.6f}°",
        f"  Assessment Date: {result.get('assessment_date', 'N/A')}",
        "=" * 70,
    ]
    return "\n".join(lines)


def _scores_section(result: dict) -> str:
    lines = [
        "",
        "SECTION 1 — RISK SCORES (Scale: 0 = lowest risk, 100 = highest risk)",
        "-" * 70,
        f"  Flood Risk Score      : {result.get('flood_risk_score', 0):.1f} / 100"
        f"  [{result.get('flood_risk_tier', 'N/A')}]",
        f"  Heat Risk Score       : {result.get('heat_risk_score', 0):.1f} / 100"
        f"  [{result.get('heat_risk_tier', 'N/A')}]",
        f"  Water Stress Score    : {result.get('water_risk_score', 0):.1f} / 100"
        f"  [{result.get('water_risk_tier', 'N/A')}]",
        f"  Multi-Hazard Score    : {result.get('hazard_score', 0):.1f} / 100",
        "",
        f"  ▶ OVERALL RISK SCORE  : {result.get('overall_risk_score', 0):.1f} / 100"
        f"  [{result.get('overall_risk_tier', 'N/A')}]",
        "",
        "  Tier definitions:",
        "    LOW       : 0–25   (minimal expected impact)",
        "    MEDIUM    : 25–50  (moderate adaptation recommended)",
        "    HIGH      : 50–75  (significant risk; urgent measures advised)",
        "    VERY HIGH : 75–100 (critical exposure; immediate action required)",
    ]
    return "\n".join(lines)


def _data_sources_section(result: dict) -> str:
    ds = result.get("data_sources", {})
    th_error = ds.get("thinkhazard", {}).get("lookup_error", "")
    aq_error = ds.get("aqueduct", {}).get("error", "")
    np_error = ds.get("nasa_power", {}).get("error", "")

    lines = [
        "",
        "SECTION 2 — DATA SOURCES & METHODOLOGY",
        "-" * 70,
        "  1. ThinkHazard (GFDRR / World Bank)",
        "     URL: https://thinkhazard.org",
        "     Data: Multi-hazard assessment (flood, earthquake, cyclone, etc.)",
        f"     Status: {'Error: ' + th_error if th_error else 'OK'}",
        "",
        "  2. Aqueduct Water Risk Atlas (World Resources Institute)",
        "     URL: https://www.wri.org/aqueduct",
        "     Data: Baseline water stress score (0–5 scale → normalised 0–100)",
        f"     Status: {'Error: ' + aq_error if aq_error else 'OK'}",
        "",
        "  3. NASA POWER Climatology API",
        "     URL: https://power.larc.nasa.gov",
        "     Data: Monthly/annual temperature (T2M, T2M_MAX) & precipitation",
        f"     Status: {'Error: ' + np_error if np_error else 'OK'}",
        "",
        "  Scoring Methodology: Rules-based weighted composite.",
        "    Overall = 0.35×Flood + 0.30×Heat + 0.25×Water + 0.10×MultiHazard",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Framework-specific disclosure sections
# ---------------------------------------------------------------------------

def _tcfd_section(result: dict) -> str:
    tier = result.get("overall_risk_tier", "MEDIUM")
    return "\n".join([
        "",
        "SECTION 3 — TCFD DISCLOSURE (Physical Risk)",
        "-" * 70,
        "  Pillar: Risk Management / Metrics & Targets",
        f"  Risk Category: Physical — Acute & Chronic",
        f"  Overall Risk Rating: {tier}",
        "",
        "  Acute Physical Risks Assessed:",
        "    • Riverine and coastal flood events",
        "    • Extreme heat episodes (wet-bulb temperature exceedance)",
        "    • Tropical cyclone / windstorm exposure",
        "",
        "  Chronic Physical Risks Assessed:",
        "    • Long-term temperature increase (mean & max)",
        "    • Shifting precipitation patterns and drought frequency",
        "    • Chronic water stress and scarcity",
        "",
        "  Scenario Alignment Recommended:",
        "    • SSP1-2.6 (well-below 2°C) — optimistic",
        "    • SSP2-4.5 (intermediate) — central case",
        "    • SSP5-8.5 (high emissions) — downside",
        "",
        "  " + result.get("narrative", ""),
    ])


def _issb_section(result: dict) -> str:
    tier = result.get("overall_risk_tier", "MEDIUM")
    return "\n".join([
        "",
        "SECTION 3 — IFRS S2 DISCLOSURE (Physical Climate Risk)",
        "-" * 70,
        "  Standard: IFRS S2 Climate-related Disclosures (ISSB, June 2023)",
        "  Paragraphs: 29–30 (Physical Risk), B8–B25 (Guidance)",
        f"  Physical Risk Level: {tier}",
        "",
        "  Climate-related risks identified (IFRS S2 §10):",
        "    • Acute: Flooding, extreme heat, water scarcity episodes",
        "    • Chronic: Rising temperatures, changed precipitation regimes",
        "",
        "  Climate resilience assessment (IFRS S2 §22):",
        "    Scenario analysis recommended under 1.5°C and 4°C warming pathways.",
        "    Time horizons: short (≤5 yr), medium (5–10 yr), long (>10 yr).",
        "",
        "  " + result.get("narrative", ""),
    ])


def _brsr_section(result: dict) -> str:
    tier = result.get("overall_risk_tier", "MEDIUM")
    return "\n".join([
        "",
        "SECTION 3 — SEBI BRSR DISCLOSURE (Climate Risk — Leadership Indicator)",
        "-" * 70,
        "  Framework: Business Responsibility and Sustainability Report (SEBI)",
        "  Principle: 6 — Respect and Make Efforts to Protect the Environment",
        "  Indicator Type: Leadership (voluntary, beyond mandatory)",
        f"  Climate Risk Level: {tier}",
        "",
        "  BRSR Core ESG Attributes Addressed:",
        "    • GHG emissions context: physical risk to emission-intensive assets",
        "    • Water intensity: water stress score informs water management KPIs",
        "    • Business continuity: flood and heat risk to supply chain assets",
        "",
        "  Recommended disclosure location: BRSR, Section C, Principle 6,",
        "  'Risks and Opportunities from Climate Change' (Annual Report).",
        "",
        "  " + result.get("narrative", ""),
    ])


def _csrd_section(result: dict) -> str:
    tier = result.get("overall_risk_tier", "MEDIUM")
    return "\n".join([
        "",
        "SECTION 3 — CSRD / ESRS E1 DISCLOSURE (Physical Climate Risk)",
        "-" * 70,
        "  Directive: EU CSRD 2022/2464 / ESRS E1 — Climate Change",
        "  Disclosure Requirement: ESRS E1-9 (Physical climate-related risks)",
        f"  Physical Risk Level: {tier}",
        "",
        "  ESRS E1-9 Disclosure Elements Covered:",
        "    • Identification of physical climate hazards",
        "    • Exposure of assets/operations to acute and chronic risks",
        "    • Time horizons: 2030, 2040, 2050",
        "    • Alignment with EU Taxonomy climate risk and vulnerability assessment",
        "",
        "  Applicable to: In-scope entities under CSRD (large EU companies,",
        "  listed SMEs from 2026, and third-country companies from 2028).",
        "",
        "  Climate scenarios referenced:",
        "    • RCP 2.6 / SSP1 — 1.5°C pathway",
        "    • RCP 8.5 / SSP5 — 4°C pathway",
        "",
        "  " + result.get("narrative", ""),
    ])


def _disclaimer() -> str:
    return "\n".join([
        "",
        "=" * 70,
        "  DISCLAIMER",
        "-" * 70,
        "  This report is generated by the ClimateRisk Pro QGIS plugin using",
        "  publicly available third-party datasets (ThinkHazard, WRI Aqueduct,",
        "  NASA POWER). It is intended as a screening tool only and should not",
        "  be relied upon as a substitute for a full site-specific climate risk",
        "  assessment conducted by a qualified professional. Scores are indicative",
        "  and subject to data availability and model uncertainty.",
        "",
        "  Data providers retain all rights to their underlying datasets.",
        "  Plugin source: https://github.com/Creator619-Python/climaterisk-pro",
        "=" * 70,
    ])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_report_text(result: dict, framework: str) -> str:
    """Assemble the full plain-text report for the given framework."""
    sections = [
        _header(result, framework),
        _scores_section(result),
        _data_sources_section(result),
    ]

    fw = framework.upper()
    if fw == "TCFD":
        sections.append(_tcfd_section(result))
    elif fw in ("ISSB S2", "ISSB"):
        sections.append(_issb_section(result))
    elif fw == "BRSR":
        sections.append(_brsr_section(result))
    elif fw == "CSRD":
        sections.append(_csrd_section(result))
    else:
        sections.append("\n" + result.get("narrative", ""))

    sections.append(_disclaimer())
    return "\n".join(sections) + "\n"


def export_report(result: dict, framework: str, parent=None):
    """
    Open a save-file dialog and write the report to the chosen path.
    Called from plugin.py when the user clicks 'Export Report'.
    """
    location = result.get("location_name", "location").replace(" ", "_").replace(",", "")
    fw_slug = framework.replace(" ", "_")
    default_name = f"ClimateRisk_{fw_slug}_{location}.txt"

    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save ClimateRisk Pro Report",
        default_name,
        "Text files (*.txt);;All files (*)",
    )

    if not path:
        return  # user cancelled

    try:
        report_text = build_report_text(result, framework)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report_text)
        QMessageBox.information(
            parent,
            "Report Saved",
            f"Report saved to:\n{path}",
        )
    except OSError as e:
        QMessageBox.critical(
            parent,
            "Export Failed",
            f"Could not save report:\n{e}",
        )
