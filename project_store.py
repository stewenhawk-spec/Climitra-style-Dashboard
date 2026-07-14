"""
project_store.py — a tiny helper so every page reads/writes project data
the SAME way, instead of scattering st.session_state[...] typos everywhere.

Nothing here is saved permanently — it all lives in st.session_state, which
means it resets if the browser tab is refreshed or the server restarts.
That's fine for a prototype; a real version would save this to a database
instead (see the note in main README about Supabase/Postgres).
"""

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
