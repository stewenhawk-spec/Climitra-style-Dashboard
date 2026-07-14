"""
Biochar dMRV Dashboard — Phase 3 (styled)
=================================
Thin UI layer over vm0044_engine.run_project(). A developer uploads their
project's five data tables (matching the standard template), clicks Run,
and gets back the batch ledger, project summary, and QA/satellite flags —
no coding required on their end.

To run locally:
    pip install streamlit pandas numpy pyyaml plotly
    streamlit run app.py

To deploy so others can use it without installing anything:
    Push this folder to a GitHub repo, then deploy free at
    https://share.streamlit.io (Streamlit Community Cloud).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from vm0044_engine import run_project
from sheets_connector import read_worksheet

# ---------------------------------------------------------------------------
# THEME — blue / green, applied via CSS on top of native Streamlit widgets.
# Streamlit doesn't allow full custom layout, so this styles the existing
# widgets (metrics, buttons, tabs, sidebar) rather than replacing them.
# ---------------------------------------------------------------------------

PRIMARY_BLUE = "#1B5E8C"
DEEP_BLUE = "#123F5E"
ACCENT_GREEN = "#2E9E5B"
SLATE = "#5C7A99"
AMBER = "#C98A1B"
BG = "#F6F8FA"
CARD_BORDER = "#E1E6EA"
TEXT_DARK = "#1A2B33"
TEXT_MUTED = "#5C6B73"

st.set_page_config(page_title="Biochar dMRV Dashboard", page_icon="🌱", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    color: {TEXT_DARK};
}}
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {DEEP_BLUE};
}}
.stApp {{ background-color: {BG}; }}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background-color: {DEEP_BLUE};
}}
section[data-testid="stSidebar"] * {{ color: #EAF1F6 !important; }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: #FFFFFF !important; }}
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {{
    color: {TEXT_DARK} !important;
}}

/* Header banner */
.dmrv-header {{
    border-left: 5px solid {ACCENT_GREEN};
    background: #FFFFFF;
    padding: 18px 24px;
    border-radius: 6px;
    border: 1px solid {CARD_BORDER};
    margin-bottom: 22px;
}}
.dmrv-header h1 {{ margin: 0 0 4px 0; font-size: 26px; }}
.dmrv-header p {{ margin: 0; color: {TEXT_MUTED}; font-size: 14px; }}
.dmrv-badge {{
    display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; background: #EAF4EE; color: {ACCENT_GREEN};
    padding: 3px 10px; border-radius: 20px; margin-top: 10px;
}}

/* Metric cards */
div[data-testid="stMetric"] {{
    background: #FFFFFF; border: 1px solid {CARD_BORDER}; border-radius: 6px;
    padding: 14px 16px 10px 16px; border-top: 3px solid {PRIMARY_BLUE};
}}
div[data-testid="stMetricLabel"] {{ color: {TEXT_MUTED}; font-size: 12.5px; }}
div[data-testid="stMetricValue"] {{ color: {DEEP_BLUE}; font-family: 'Space Grotesk', sans-serif; }}

/* Buttons */
.stButton > button {{
    background-color: {PRIMARY_BLUE}; color: #FFFFFF; border: none;
    font-weight: 600; border-radius: 5px;
}}
.stButton > button:hover {{ background-color: {DEEP_BLUE}; color: #FFFFFF; }}
.stDownloadButton > button {{
    background-color: {ACCENT_GREEN}; color: #FFFFFF; border: none; font-weight: 600;
    border-radius: 5px;
}}
.stDownloadButton > button:hover {{ background-color: #217A46; color: #FFFFFF; }}

/* Tabs */
button[data-baseweb="tab"] {{ font-weight: 600; color: {TEXT_MUTED}; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: {PRIMARY_BLUE}; }}
div[data-baseweb="tab-highlight"] {{ background-color: {PRIMARY_BLUE}; }}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dmrv-header">
    <h1>Biochar dMRV Dashboard</h1>
    <p>Upload your project's data tables and get a VM0044-calculated, audit-trail-ready
    emission reduction estimate — pending VVB verification.</p>
    <span class="dmrv-badge">VM0044 v1.1 · Low-Tech Pathway (P.2)</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR: project identity + file uploads
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("1. Project")
    project_id = st.text_input("Project ID", placeholder="e.g. PROJ-DELHI-001")

    st.header("2. Data source")
    data_source = st.radio(
        "Where should data come from?",
        ["Upload CSV files", "Pull from Google Sheets (live)"],
        help="Live pull reads directly from your Google Sheet — no export/upload step needed."
    )

    feedstock_file = pyrolysis_file = lab_file = application_file = biomass_file = None
    gs_config = None

    if data_source == "Upload CSV files":
        st.caption("CSV files matching the standard template tabs.")
        feedstock_file = st.file_uploader("Suppliers & Feedstocks", type="csv")
        pyrolysis_file = st.file_uploader("Pyrolysis Batches", type="csv")
        lab_file = st.file_uploader("Lab Data", type="csv")
        application_file = st.file_uploader("Soil Application", type="csv")
        biomass_file = st.file_uploader(
            "Biomass Sourcing (GEE) — optional", type="csv",
            help="Skip this if you don't have satellite-based sourcing data yet. "
                 "The satellite over-harvest and confidence checks will be skipped."
        )
    else:
        st.caption("Reads live from the Sheet ID and tab names in config/defaults.yaml.")
        try:
            with open("config/defaults.yaml") as f:
                gs_config = yaml.safe_load(f)["google_sheets"]
            st.success(f"Config loaded — Sheet ID: `{gs_config['sheet_id'][:12]}...`")
        except Exception as e:
            st.error(f"Couldn't load config/defaults.yaml: {e}")

    st.header("3. Methodology settings (optional)")
    st.caption("Leave blank to use Verra's default values.")
    grid_ef_override = st.number_input(
        "Grid emission factor (kg CO2/kWh)", min_value=0.0, value=0.0, step=0.01,
        help="Leave at 0 to use the shared default (0.71). Enter your project country's "
             "actual grid factor for a more accurate result."
    )

    run_clicked = st.button("Run calculation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# MAIN: run the engine and render results
# ---------------------------------------------------------------------------

if data_source == "Upload CSV files":
    required_files = {
        "Suppliers & Feedstocks": feedstock_file,
        "Pyrolysis Batches": pyrolysis_file,
        "Lab Data": lab_file,
        "Soil Application": application_file,
    }
else:
    required_files = {}  # live pull checks happen separately below

if run_clicked:
    if not project_id:
        st.error("Enter a Project ID before running.")
    elif data_source == "Upload CSV files" and any(f is None for f in required_files.values()):
        missing = [name for name, f in required_files.items() if f is None]
        st.error(f"Missing required files: {', '.join(missing)}")
    elif data_source == "Pull from Google Sheets (live)" and gs_config is None:
        st.error("Google Sheets config didn't load — check config/defaults.yaml.")
    else:
        if data_source == "Upload CSV files":
            feedstock_df = pd.read_csv(feedstock_file)
            pyrolysis_df = pd.read_csv(pyrolysis_file)
            lab_df = pd.read_csv(lab_file)
            application_df = pd.read_csv(application_file)
            biomass_df = pd.read_csv(biomass_file) if biomass_file is not None else None
        else:
            sheet_id = gs_config["sheet_id"]
            creds_path = gs_config["credentials_path"]
            ws = gs_config["worksheets"]
            try:
                feedstock_df = read_worksheet(sheet_id, ws["feedstock"], creds_path)
                pyrolysis_df = read_worksheet(sheet_id, ws["pyrolysis"], creds_path)
                lab_df = read_worksheet(sheet_id, ws["lab"], creds_path)
                application_df = read_worksheet(sheet_id, ws["application"], creds_path)
                biomass_df = (
                    read_worksheet(sheet_id, ws["biomass"], creds_path)
                    if "biomass" in ws else None
                )
            except Exception as e:
                st.error(f"Couldn't read from Google Sheets: {e}")
                st.stop()

        config_overrides = None
        if grid_ef_override > 0:
            config_overrides = {"emission_factors": {"grid_ef_kgco2_per_kwh": grid_ef_override}}

        try:
            result = run_project(
                project_id=project_id,
                feedstock_df=feedstock_df,
                pyrolysis_df=pyrolysis_df,
                lab_df=lab_df,
                application_df=application_df,
                biomass_df=biomass_df,
                config_overrides=config_overrides,
            )
        except Exception as e:
            st.error(f"Calculation failed: {e}")
            st.info(
                "This usually means a column name in your CSV doesn't match what the "
                "engine expects. Check the template column headers and try again."
            )
            st.stop()

        st.success(f"Calculated results for **{project_id}**")

        summary = result["summary"]
        ledger = result["ledger"]

        # --- Top-line metrics (styled via CSS above) ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net tCO2e", summary["net_tCO2e_project"])
        c2.metric("Gross removed", summary["gross_co2e_removed"])
        c3.metric("Project emissions", summary["total_project_emissions"])
        c4.metric("Leakage", summary["total_leakage"])

        c5, c6, c7 = st.columns(3)
        c5.metric("Total batches", summary["total_batches"])
        c6.metric("Eligible batches", summary["eligible_batches"])
        flagged_total = summary["batches_flagged_mass_balance"] + summary["batches_flagged_missing_lab"]
        c7.metric("Flagged batches", flagged_total,
                   delta=None if flagged_total == 0 else f"{flagged_total} need review",
                   delta_color="inverse")

        st.write("")

        tab_summary, tab_ledger, tab_qa, tab_sat = st.tabs(
            ["📊  Summary & Charts", "📋  Batch Ledger", "🚩  QA Flags", "🛰️  Satellite Sourcing QA"]
        )

        # -----------------------------------------------------------------
        # TAB: Summary & Charts
        # -----------------------------------------------------------------
        with tab_summary:
            v1, v2 = st.columns([1, 1])

            with v1:
                elig_counts = pd.DataFrame({
                    "Status": ["Eligible", "Ineligible"],
                    "Batches": [summary["eligible_batches"], summary["ineligible_batches"]],
                })
                fig_donut = px.pie(
                    elig_counts, names="Status", values="Batches", hole=0.55,
                    color="Status",
                    color_discrete_map={"Eligible": ACCENT_GREEN, "Ineligible": SLATE},
                    title="Batch Eligibility",
                )
                fig_donut.update_traces(textinfo="value+percent")
                fig_donut.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320,
                                         font=dict(family="Inter, sans-serif"))
                st.plotly_chart(fig_donut, use_container_width=True)

            with v2:
                fig_bar = px.bar(
                    ledger, x="batch_id", y="net_tCO2e", color="soil_eligible",
                    color_discrete_map={True: ACCENT_GREEN, False: SLATE},
                    labels={"batch_id": "Batch", "net_tCO2e": "Net tCO2e", "soil_eligible": "Eligible"},
                    title="Net tCO2e by Batch",
                )
                fig_bar.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320,
                                       font=dict(family="Inter, sans-serif"))
                st.plotly_chart(fig_bar, use_container_width=True)

            eligible_ledger = ledger[ledger["soil_eligible"] == True]
            if len(eligible_ledger) > 0:
                breakdown = eligible_ledger[[
                    "batch_id", "co2e_removed_gross", "pe_energy_tCO2e",
                    "pe_methane_tCO2e", "leakage_transport_tCO2e"
                ]].melt(id_vars="batch_id", var_name="Component", value_name="tCO2e")
                component_labels = {
                    "co2e_removed_gross": "Gross CO2e removed",
                    "pe_energy_tCO2e": "Energy emissions",
                    "pe_methane_tCO2e": "Methane emissions",
                    "leakage_transport_tCO2e": "Transport leakage",
                }
                breakdown["Component"] = breakdown["Component"].map(component_labels)
                fig_stack = px.bar(
                    breakdown, x="batch_id", y="tCO2e", color="Component", barmode="group",
                    title="Emissions Breakdown by Batch (eligible batches only)",
                    color_discrete_sequence=[ACCENT_GREEN, PRIMARY_BLUE, "#7FB3D5", AMBER],
                )
                fig_stack.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=360,
                                         font=dict(family="Inter, sans-serif"))
                st.plotly_chart(fig_stack, use_container_width=True)

        # -----------------------------------------------------------------
        # TAB: Batch Ledger
        # -----------------------------------------------------------------
        with tab_ledger:
            st.dataframe(ledger, use_container_width=True)
            st.download_button(
                "Download batch ledger (CSV)",
                ledger.to_csv(index=False),
                file_name=f"{project_id}_batch_ledger.csv",
            )

        # -----------------------------------------------------------------
        # TAB: QA Flags
        # -----------------------------------------------------------------
        with tab_qa:
            if len(result["qa_flags"]) == 0:
                st.success("No batch-level QA issues found.")
            else:
                st.warning(f"{len(result['qa_flags'])} batch(es) flagged — review before submission.")
                st.dataframe(result["qa_flags"], use_container_width=True)

        # -----------------------------------------------------------------
        # TAB: Satellite Sourcing QA
        # -----------------------------------------------------------------
        with tab_sat:
            if "satellite_sourcing_qa" in result:
                sat = result["satellite_sourcing_qa"]
                over_harvest_count = (sat["over_harvest_flag"] == "OVER-HARVEST").sum()
                low_conf_count = (sat["low_confidence_flag"] == "LOW CONFIDENCE").sum()
                if over_harvest_count == 0 and low_conf_count == 0:
                    st.success("No sourcing issues found against satellite biomass estimates.")
                else:
                    st.warning(
                        f"{over_harvest_count} over-harvest flag(s), "
                        f"{low_conf_count} low-confidence classification flag(s)."
                    )
                st.dataframe(sat, use_container_width=True)

                sat_plot = sat.dropna(subset=["est_total_biomass_t"]).copy()
                if len(sat_plot) > 0:
                    sat_plot["flag"] = sat_plot["over_harvest_flag"].where(
                        sat_plot["over_harvest_flag"] == "OVER-HARVEST", sat_plot["low_confidence_flag"]
                    )
                    sat_plot["flag"] = sat_plot["flag"].replace("OK", "Within bounds")
                    max_val = max(sat_plot["weight_delivered_t"].max(), sat_plot["est_total_biomass_t"].max()) * 1.1

                    fig_sat = go.Figure()
                    fig_sat.add_trace(go.Scatter(
                        x=[0, max_val], y=[0, max_val], mode="lines",
                        line=dict(dash="dash", color="#9AA5AB"), name="Delivered = Estimated",
                        hoverinfo="skip",
                    ))
                    fig_sat.add_trace(go.Scatter(
                        x=sat_plot["est_total_biomass_t"], y=sat_plot["weight_delivered_t"],
                        mode="markers+text", text=sat_plot["gee_plot_id"], textposition="top center",
                        marker=dict(
                            size=14,
                            color=sat_plot["flag"].map({
                                "OVER-HARVEST": AMBER,
                                "LOW CONFIDENCE": "#E0B356",
                                "Within bounds": ACCENT_GREEN,
                            }),
                        ),
                        name="Feedstock delivery",
                    ))
                    fig_sat.update_layout(
                        title="Delivered Weight vs Satellite Biomass Estimate (per plot)",
                        xaxis_title="Satellite-estimated biomass (t)",
                        yaxis_title="Weight delivered (t)",
                        margin=dict(t=50, b=10, l=10, r=10), height=380,
                        font=dict(family="Inter, sans-serif"),
                    )
                    st.plotly_chart(fig_sat, use_container_width=True)
                    st.caption(
                        "Points above the dashed line delivered more than the satellite estimate "
                        "suggests was available on that plot. 🟠 over-harvest · 🟡 low classification "
                        "confidence · 🟢 within bounds."
                    )
            else:
                st.caption("No satellite sourcing file uploaded — sourcing checks skipped.")

else:
    st.info("Upload your project's files in the sidebar and click **Run calculation**.")