"""
views/projects.py — where you create a project, upload its data files, and
run the real VM0044 calculation (same engine as the original app.py).

Results get saved into project_store so the Home tab can display them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from vm0044_engine import run_project
import project_store as store

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

    st.subheader("Data files")
    st.caption("CSV files matching the standard template tabs — same files your old app.py used.")
    feedstock_file = st.file_uploader("Suppliers & Feedstocks", type="csv", key="p_feed")
    pyrolysis_file = st.file_uploader("Pyrolysis Batches", type="csv", key="p_pyro")
    lab_file = st.file_uploader("Lab Data", type="csv", key="p_lab")
    application_file = st.file_uploader("Soil Application", type="csv", key="p_app")
    biomass_file = st.file_uploader(
        "Biomass Sourcing (GEE) — optional", type="csv", key="p_bio",
        help="Skip this if you don't have satellite sourcing data yet."
    )

    grid_ef_override = st.number_input(
        "Grid emission factor override (kg CO2/kWh)", min_value=0.0, value=0.0, step=0.01,
        help="Leave at 0 to use the shared default (0.71)."
    )

    if st.button("Run calculation", type="primary"):
        required = {
            "Suppliers & Feedstocks": feedstock_file,
            "Pyrolysis Batches": pyrolysis_file,
            "Lab Data": lab_file,
            "Soil Application": application_file,
        }
        missing = [name for name, f in required.items() if f is None]

        if not project_id:
            st.error("Enter a Project ID before running.")
        elif missing:
            st.error(f"Missing required files: {', '.join(missing)}")
        else:
            feedstock_df = pd.read_csv(feedstock_file)
            pyrolysis_df = pd.read_csv(pyrolysis_file)
            lab_df = pd.read_csv(lab_file)
            application_df = pd.read_csv(application_file)
            biomass_df = pd.read_csv(biomass_file) if biomass_file is not None else None

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
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    project_ids = list(all_projects.keys())
    current = st.session_state.get("current_project")
    default_index = project_ids.index(current) if current in project_ids else 0

    selected = st.selectbox("Select a project to view in detail", project_ids, index=default_index)

    if selected != current:
        if st.button(f"Show {selected} on Home tab"):
            store.set_current_project(selected)
            st.rerun()

    with st.expander(f"Full ledger & QA flags — {selected}"):
        result = all_projects[selected]["result"]
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
