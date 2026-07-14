"""
views/home.py — the main landing page, now wired to real project data.

If no project has been calculated yet, this page tells you to go run one
on the Projects tab instead of showing fake numbers.
"""

import sys
from pathlib import Path

# Make sure the project root (one level up from views/) is importable,
# regardless of how Streamlit launched this page.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import folium
import streamlit as st
from streamlit_folium import st_folium

import project_store as store

st.title("Home")

project = store.get_current_project()

if project is None:
    st.info(
        "No project loaded yet. Go to the **Projects** tab, upload your data "
        "files, and click **Run calculation** — results will show up here."
    )
else:
    summary = project["result"]["summary"]
    ledger = project["result"]["ledger"]
    total_biochar_t = ledger["dry_biochar_mass_t"].sum()
    flagged = summary["batches_flagged_mass_balance"] + summary["batches_flagged_missing_lab"]

    # --- KPI cards, now from the real calculation -----------------------
    k1, k2, k3 = st.columns(3)
    k1.metric("Total biochar produced", f"{total_biochar_t:.2f} t")
    k2.metric("Net verified emissions", f"{summary['net_tCO2e_project']} tCO2e")
    k3.metric("Flagged / unverified batches", flagged,
              delta=None if flagged == 0 else f"{flagged} need review",
              delta_color="inverse")

    st.divider()
    st.subheader("Project Overview")

    map_col, info_col = st.columns([1.3, 1])

    with map_col:
        m = folium.Map(location=[project["lat"], project["lon"]], zoom_start=10,
                        tiles="OpenStreetMap")
        folium.Marker(
            [project["lat"], project["lon"]],
            tooltip="Facility",
            icon=folium.Icon(color="red", icon="fire", prefix="fa"),
        ).add_to(m)
        st_folium(m, height=340, use_container_width=True)

    with info_col:
        for label, value in project["meta"].items():
            c1, c2 = st.columns([1, 1.3])
            c1.markdown(f"<span style='color:#5C6B73;font-size:13px;'>{label}</span>",
                        unsafe_allow_html=True)
            c2.markdown(f"**{value}**")

    st.caption("Full batch ledger, QA flags, and charts for this project are on the "
               "**Projects** tab.")
