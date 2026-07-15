"""
client_registry.py — remembers each CLIENT's Google Sheet ID so you don't
have to paste it in every time you run a calculation for them.

Same pattern as project_store.py: lives in st.session_state, so it resets
if the browser tab is refreshed or the server restarts. That's why
views/settings.py also gives you an Export/Import (JSON) button — export
your client list once you've set it up, and re-import it next session
instead of re-typing every Sheet ID.

One client = one Google Sheet (their own copy of your template, with the
same 5 tabs: Suppliers & Feedstocks, Pyrolysis Batches, Lab_data,
Soil Application, Biomass_Sourcing_GEE). Multiple projects CAN point at
the same client if you ever re-run a calc for them, but typically it's
one client -> one sheet -> one (or a few) projects.
"""

import json

import streamlit as st


def _ensure():
    if "clients" not in st.session_state:
        st.session_state["clients"] = {}  # client_name -> {"sheet_id": str, "notes": str}


def save_client(client_name: str, sheet_id: str, notes: str = ""):
    """Registers or updates a client's Sheet ID."""
    _ensure()
    st.session_state["clients"][client_name] = {"sheet_id": sheet_id.strip(), "notes": notes}


def get_all_clients() -> dict:
    _ensure()
    return st.session_state["clients"]


def get_client(client_name: str):
    _ensure()
    return st.session_state["clients"].get(client_name)


def delete_client(client_name: str):
    _ensure()
    st.session_state["clients"].pop(client_name, None)


def export_json() -> str:
    """Returns the whole registry as a JSON string, for the download button."""
    _ensure()
    return json.dumps(st.session_state["clients"], indent=2)


def import_json(json_text: str, overwrite: bool = False):
    """
    Loads a previously-exported client list back in.
    overwrite=False (default) merges with whatever's already registered
    this session; overwrite=True replaces the registry entirely.
    """
    _ensure()
    incoming = json.loads(json_text)
    if overwrite:
        st.session_state["clients"] = incoming
    else:
        st.session_state["clients"].update(incoming)
