"""
project_store.py — a tiny helper so every page reads/writes project data
the SAME way, instead of scattering st.session_state[...] typos everywhere.

Nothing here is saved permanently — it all lives in st.session_state, which
means it resets if the browser tab is refreshed or the server restarts.
That's fine for a prototype; a real version would save this to a database
instead (see the note in main README about Supabase/Postgres).

UPDATE: added export_json()/import_json() below, same pattern as
client_registry.py — export after a batch of calculations, re-import at
the start of your next session instead of re-running everything. This is
a stopgap, not a substitute for a real DB — it only protects you if you
remember to export before closing the tab / redeploying.
"""

import json

import pandas as pd
import streamlit as st


def _ensure():
    if "projects" not in st.session_state:
        st.session_state["projects"] = {}          # project_id -> data dict
    if "current_project" not in st.session_state:
        st.session_state["current_project"] = None  # which one Home shows


def save_project(project_id: str, data: dict):
    """Stores a calculated project and makes it the one shown on Home."""
    _ensure()
    st.session_state["projects"][project_id] = data
    st.session_state["current_project"] = project_id


def get_all_projects() -> dict:
    _ensure()
    return st.session_state["projects"]


def get_current_project():
    """Returns the full data dict for whichever project is 'active', or None."""
    _ensure()
    pid = st.session_state["current_project"]
    if pid is None:
        return None
    return st.session_state["projects"].get(pid)


def set_current_project(project_id: str):
    _ensure()
    st.session_state["current_project"] = project_id


# ---------------------------------------------------------------------------
# Export / import (same pattern as client_registry.py)
# ---------------------------------------------------------------------------

def _json_default(obj):
    """Lets json.dumps handle the DataFrames tucked inside each project's result."""
    if isinstance(obj, pd.DataFrame):
        return {"__dataframe__": True, "records": obj.to_dict("records")}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_object_hook(d):
    """Reverses _json_default on the way back in."""
    if d.get("__dataframe__"):
        return pd.DataFrame(d["records"])
    return d


def export_json() -> str:
    """Returns every stored project as a JSON string, for a download button."""
    _ensure()
    return json.dumps(st.session_state["projects"], indent=2, default=_json_default)


def import_json(json_text: str, overwrite: bool = False):
    """
    Loads a previously-exported project list back in.
    overwrite=False (default) merges with whatever's already loaded this
    session; overwrite=True replaces the whole store.
    """
    _ensure()
    incoming = json.loads(json_text, object_hook=_json_object_hook)
    if overwrite:
        st.session_state["projects"] = incoming
    else:
        st.session_state["projects"].update(incoming)
