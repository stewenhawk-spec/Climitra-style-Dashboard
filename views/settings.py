"""
views/settings.py — client registry management.

This is where you register each client's Google Sheet so the Projects tab
can pull their data live. Registry is session-state (see client_registry.py)
so use Export after setting clients up, and Import at the start of a new
session instead of re-entering every Sheet ID by hand.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import client_registry as clients

st.title("Settings")

st.subheader("Client registry")
st.caption(
    "Each client should have their own copy of the dMRV Google Sheet template "
    "(same 5 tabs: Suppliers & Feedstocks, Pyrolysis Batches, Lab_data, "
    "Soil Application, Biomass_Sourcing_GEE). Register their Sheet ID here once, "
    "then select them by name on the Projects tab."
)

all_clients = clients.get_all_clients()

if not all_clients:
    st.info("No clients registered yet. Add one below, or register one directly from the Projects tab.")
else:
    for name, record in all_clients.items():
        c1, c2, c3 = st.columns([2, 3, 1])
        c1.markdown(f"**{name}**")
        c2.code(record["sheet_id"], language=None)
        if c3.button("Remove", key=f"remove_{name}"):
            clients.delete_client(name)
            st.rerun()

st.divider()

with st.expander("➕ Register a new client"):
    c1, c2 = st.columns([1, 2])
    name = c1.text_input("Client name", key="settings_new_client_name")
    sheet_id = c2.text_input(
        "Google Sheet ID", key="settings_new_client_sheet_id",
        help="The long ID in the sheet's URL: docs.google.com/spreadsheets/d/THIS_PART/edit"
    )
    notes = st.text_input("Notes (optional)", key="settings_new_client_notes",
                           placeholder="e.g. contact, registry, project type")
    if st.button("Save client", key="settings_save_client"):
        if name and sheet_id:
            clients.save_client(name, sheet_id, notes)
            st.success(f"Registered **{name}**.")
            st.rerun()
        else:
            st.warning("Enter both a client name and their Sheet ID.")

st.divider()

st.subheader("Backup / restore client list")
st.caption(
    "The registry above lives only in this browser session — it clears if the "
    "app restarts or you open a new tab. Export it after adding clients, and "
    "import it back at the start of your next session."
)

ec1, ec2 = st.columns(2)

with ec1:
    st.download_button(
        "⬇️ Export client list (JSON)",
        clients.export_json(),
        file_name="dmrv_clients.json",
        disabled=len(all_clients) == 0,
    )

with ec2:
    uploaded = st.file_uploader("⬆️ Import client list (JSON)", type="json", key="settings_import")
    if uploaded is not None:
        overwrite = st.checkbox("Overwrite existing registry (instead of merging)", key="settings_import_overwrite")
        if st.button("Import", key="settings_do_import"):
            try:
                clients.import_json(uploaded.read().decode("utf-8"), overwrite=overwrite)
                st.success("Client list imported.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't import: {e}")

st.divider()
st.subheader("Other")
st.info("User management and registry (Verra/Puro.earth/Isometric) connection settings go here.")
