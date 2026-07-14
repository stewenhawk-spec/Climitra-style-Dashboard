"""
views/home.py — the main landing page (matches the Climitra screenshot).

This file only runs the CONTENT of the Home tab. The sidebar nav, login,
and page chrome all live in main.py — st.navigation() calls this file's
code and drops it into the content area automatically.
"""

import folium
import streamlit as st
from streamlit_folium import st_folium

st.title("Home")

# --- Date range filter (top bar in the screenshot) -------------------------
d1, d2, _ = st.columns([1, 1, 3])
d1.date_input("Production date range — from")
d2.date_input("to")

st.write("")

# --- KPI cards ---------------------------------------------------------
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Total biochar produced", "1,935 t")
with k2:
    st.metric("Verified emissions (CDR credits)", "900 tCO2e")
with k3:
    st.metric("Unverified batches", "2", delta="1 biomass ID · 1 biochar batch",
               delta_color="off")

st.divider()

# --- Project overview: map + info panel --------------------------------
st.subheader("Project Overview")

map_col, info_col = st.columns([1.3, 1])

with map_col:
    # Swap these coordinates for your actual project site (Ratdhana, Haryana
    # for example) — this is just the demo location from the screenshot.
    project_lat, project_lon = 23.03, 72.58

    m = folium.Map(location=[project_lat, project_lon], zoom_start=10, tiles="OpenStreetMap")
    folium.Marker(
        [project_lat, project_lon],
        tooltip="Facility",
        icon=folium.Icon(color="red", icon="fire", prefix="fa"),
    ).add_to(m)
    st_folium(m, height=340, use_container_width=True)

with info_col:
    project_info = {
        "Project Name": "Grasslands Revival Project, Gujarat",
        "Facility Address": "Ahmedabad, Gujarat",
        "Pyrolysis Reactor(s)": "Continuous · 2 t/hr",
        "Registry": "Verra — Pending Registration",
        "Project Start Date": "2026-03-01",
        "Project Supervisor": "—",
    }
    for label, value in project_info.items():
        c1, c2 = st.columns([1, 1.3])
        c1.markdown(f"<span style='color:#5C6B73;font-size:13px;'>{label}</span>",
                    unsafe_allow_html=True)
        c2.markdown(f"**{value}**")

    st.write("")
    st.markdown(
        "<div style='background:#F6F8FA;border:1px solid #E1E6EA;border-radius:6px;"
        "padding:12px 14px;font-size:13px;color:#5C6B73;'>"
        "<b style='color:#1A2B33;'>Project description</b><br>"
        "Converts invasive Prosopis juliflora, which has overrun native "
        "grasslands, into biochar — turning an ecological burden into a "
        "carbon removal and soil-health resource for local farms."
        "</div>",
        unsafe_allow_html=True,
    )
