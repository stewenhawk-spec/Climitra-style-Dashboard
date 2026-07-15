"""
views/projects.py — where you create a project, upload its data files, and
run the real VM0044 calculation (same engine as the original app.py).

Results get saved into project_store so the Home tab can display them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from vm0044_engine import run_project
from sheets_connector import read_worksheet
import project_store as store
import client_registry as clients

# Shared chart palette — matches the app's blue/green theme
FLAG_COLORS = {
    "OK": "#1B5E8C",
    "INELIGIBLE": "#C0392B",
    "MISSING FCp": "#C0392B",
    "OVER-ALLOCATED": "#E08E45",
    "MISSING LAB DATA": "#E08E45",
}


def _flag_color(flag: str) -> str:
    for key, color in FLAG_COLORS.items():
        if flag.startswith(key):
            return color
    return "#5C6B73"

st.title("Projects")

# ---------------------------------------------------------------------------
# Add / run a new project
# ---------------------------------------------------------------------------
with st.expander("➕ Add / run a new project", expanded=len(store.get_all_projects()) == 0):
    st.subheader("Project details")
    c1, c2 = st.columns(2)
    project_id = c1.text_input("Project ID", placeholder="e.g. PROJ-DELHI-001")
    project_name = c2.text_input("Project Name", placeholder="e.g. Ratdhana Biochar Project")

    c3, c4 = st.columns(2)
    facility_address = c3.text_input("Facility Address", placeholder="e.g. Ratdhana, Haryana")
    reactor_type = c4.text_input("Pyrolysis Reactor(s)", placeholder="e.g. Continuous · 2 t/hr")

    c5, c6, c7 = st.columns(3)
    registry = c5.selectbox("Registry", ["Verra", "Puro.earth", "Isometric"])
    start_date = c6.date_input("Project Start Date")
    supervisor = c7.text_input("Project Supervisor")

    c8, c9 = st.columns(2)
    lat = c8.number_input("Facility latitude", value=28.9400, format="%.4f")
    lon = c9.number_input("Facility longitude", value=76.9800, format="%.4f")

    st.subheader("Data source")
    data_source = st.radio(
        "Where should data come from?",
        ["Upload CSV files", "Pull from Google Sheets (live)"],
        key="p_data_source",
        help="Live pull reads directly from your Google Sheet — no export/upload step needed."
    )

    feedstock_file = pyrolysis_file = lab_file = application_file = biomass_file = None
    gs_config = None

    if data_source == "Upload CSV files":
        st.caption("CSV files matching the standard template tabs.")
        feedstock_file = st.file_uploader("Suppliers & Feedstocks", type="csv", key="p_feed")
        pyrolysis_file = st.file_uploader("Pyrolysis Batches", type="csv", key="p_pyro")
        lab_file = st.file_uploader("Lab Data", type="csv", key="p_lab")
        application_file = st.file_uploader("Soil Application", type="csv", key="p_app")
        biomass_file = st.file_uploader(
            "Biomass Sourcing (GEE) — optional", type="csv", key="p_bio",
            help="Skip this if you don't have satellite sourcing data yet."
        )
    else:
        st.caption("Reads live from that client's own Google Sheet (same 5-tab template).")

        registered = clients.get_all_clients()
        client_choice = st.selectbox(
            "Client",
            ["➕ Register a new client..."] + list(registered.keys()),
            key="p_client_choice",
        )

        if client_choice == "➕ Register a new client...":
            nc1, nc2 = st.columns([1, 2])
            new_client_name = nc1.text_input("Client name", placeholder="e.g. Tilaknagar Industries", key="p_new_client_name")
            new_client_sheet_id = nc2.text_input(
                "Their Google Sheet ID", key="p_new_client_sheet_id",
                help="The long ID in the sheet's URL: docs.google.com/spreadsheets/d/THIS_PART/edit"
            )
            if st.button("Save client", key="p_save_client"):
                if new_client_name and new_client_sheet_id:
                    clients.save_client(new_client_name, new_client_sheet_id)
                    st.success(f"Registered **{new_client_name}**. Select them above to continue.")
                    st.rerun()
                else:
                    st.warning("Enter both a client name and their Sheet ID.")
            gs_config = None
        else:
            client_record = clients.get_client(client_choice)
            try:
                with open("config/defaults.yaml") as f:
                    template = yaml.safe_load(f)["google_sheets"]
                gs_config = {
                    "sheet_id": client_record["sheet_id"],
                    "credentials_path": template["credentials_path"],
                    "worksheets": template["worksheets"],
                }
                st.success(f"Using **{client_choice}**'s sheet — `{gs_config['sheet_id'][:12]}...`")
                # Make sure the service account has been shared as an Editor
                # on each client's sheet individually — sharing your master
                # sheet doesn't cover their copy.
                st.caption("Reminder: the service account email needs Editor access on this client's sheet too.")
            except Exception as e:
                st.error(f"Couldn't load config/defaults.yaml: {e}")
                gs_config = None

    grid_ef_override = st.number_input(
        "Grid emission factor override (kg CO2/kWh)", min_value=0.0, value=0.0, step=0.01,
        help="Leave at 0 to use the shared default (0.71)."
    )

    if st.button("Run calculation", type="primary"):
        if data_source == "Upload CSV files":
            required = {
                "Suppliers & Feedstocks": feedstock_file,
                "Pyrolysis Batches": pyrolysis_file,
                "Lab Data": lab_file,
                "Soil Application": application_file,
            }
            missing = [name for name, f in required.items() if f is None]
        else:
            missing = []

        if not project_id:
            st.error("Enter a Project ID before running.")
        elif data_source == "Upload CSV files" and missing:
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
                    "This usually means a column name in your CSV doesn't match what "
                    "the engine expects — check the template headers and try again."
                )
                st.stop()

            store.save_project(project_id, {
                "meta": {
                    "Project Name": project_name or project_id,
                    "Facility Address": facility_address or "—",
                    "Pyrolysis Reactor(s)": reactor_type or "—",
                    "Registry": registry,
                    "Project Start Date": str(start_date),
                    "Project Supervisor": supervisor or "—",
                },
                "lat": lat,
                "lon": lon,
                "result": result,
            })
            st.success(f"Calculated and saved **{project_id}**. It's now shown on the Home tab.")
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Saved projects
# ---------------------------------------------------------------------------
st.subheader("Saved projects")
all_projects = store.get_all_projects()

if not all_projects:
    st.info("No projects yet — use the form above to run your first calculation.")
else:
    rows = []
    for pid, data in all_projects.items():
        s = data["result"]["summary"]
        rows.append({
            "Project ID": pid,
            "Name": data["meta"]["Project Name"],
            "Net tCO2e": s["net_tCO2e_project"],
            "Total batches": s["total_batches"],
            "Eligible batches": s["eligible_batches"],
        })
    projects_df = pd.DataFrame(rows)
    st.dataframe(projects_df, use_container_width=True)

    if len(projects_df) > 1:
        fig_compare = px.bar(
            projects_df, x="Project ID", y="Net tCO2e", color="Project ID",
            text="Net tCO2e", title="Net tCO2e removed — by project",
        )
        fig_compare.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_compare.update_layout(showlegend=False, height=340,
                                   margin=dict(t=40, b=10, l=10, r=10))
        st.plotly_chart(fig_compare, use_container_width=True)

    project_ids = list(all_projects.keys())
    current = st.session_state.get("current_project")
    default_index = project_ids.index(current) if current in project_ids else 0

    selected = st.selectbox("Select a project to view in detail", project_ids, index=default_index)

    if selected != current:
        if st.button(f"Show {selected} on Home tab"):
            store.set_current_project(selected)
            st.rerun()

    st.divider()
    st.subheader(f"Visual analytics — {selected}")

    result = all_projects[selected]["result"]
    ledger = result["ledger"]
    summary = result["summary"]

    vc1, vc2 = st.columns(2)

    with vc1:
        st.markdown("**Net tCO2e by batch**")
        fig_batches = px.bar(
            ledger, x="batch_id", y="net_tCO2e", color="flag",
            color_discrete_map={f: _flag_color(f) for f in ledger["flag"].unique()},
        )
        fig_batches.update_layout(height=360, margin=dict(t=10, b=10, l=10, r=10),
                                   xaxis_title=None, yaxis_title="tCO2e", legend_title=None)
        st.plotly_chart(fig_batches, use_container_width=True)

    with vc2:
        st.markdown("**Removals vs. emissions vs. leakage**")
        fig_water = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["Gross removed", "Project emissions", "Transport leakage", "Net tCO2e"],
            y=[summary["gross_co2e_removed"], -summary["total_project_emissions"],
               -summary["total_leakage"], summary["net_tCO2e_project"]],
            connector={"line": {"color": "#B7C0C7"}},
            increasing={"marker": {"color": "#1B5E8C"}},
            decreasing={"marker": {"color": "#C0392B"}},
            totals={"marker": {"color": "#123F5E"}},
        ))
        fig_water.update_layout(height=360, margin=dict(t=10, b=10, l=10, r=10),
                                 yaxis_title="tCO2e", showlegend=False)
        st.plotly_chart(fig_water, use_container_width=True)

    vc3, vc4 = st.columns(2)

    with vc3:
        st.markdown("**Batch eligibility**")
        elig_df = pd.DataFrame({
            "Status": ["Eligible", "Ineligible"],
            "Batches": [summary["eligible_batches"], summary["ineligible_batches"]],
        })
        fig_elig = px.pie(elig_df, names="Status", values="Batches", hole=0.55,
                           color="Status",
                           color_discrete_map={"Eligible": "#1B5E8C", "Ineligible": "#C0392B"})
        fig_elig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_elig, use_container_width=True)

    with vc4:
        st.markdown("**Dry biochar mass by batch**")
        fig_mass = px.bar(
            ledger, x="batch_id", y="dry_biochar_mass_t",
        )
        fig_mass.update_traces(marker_color="#1B5E8C")
        fig_mass.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10),
                                xaxis_title=None, yaxis_title="tonnes (dry)")
        st.plotly_chart(fig_mass, use_container_width=True)

    with st.expander(f"Full ledger & QA flags — {selected}"):
        st.dataframe(result["ledger"], use_container_width=True)
        st.download_button(
            "Download batch ledger (CSV)",
            result["ledger"].to_csv(index=False),
            file_name=f"{selected}_batch_ledger.csv",
        )

        if len(result["qa_flags"]) == 0:
            st.success("No batch-level QA issues found.")
        else:
            st.warning(f"{len(result['qa_flags'])} batch(es) flagged — review before submission.")
            st.dataframe(result["qa_flags"], use_container_width=True)

        if "satellite_sourcing_qa" in result:
            st.markdown("**Satellite sourcing QA**")
            st.dataframe(result["satellite_sourcing_qa"], use_container_width=True)
