"""views/audit_log.py — placeholder for the immutable audit trail tab."""

import streamlit as st

st.title("Audit Log")
st.info(
    "This is where every batch edit, sync event, and verification action "
    "would show up as an append-only list (never deleted, only added to). "
    "For a real version, this table should read from a database table you "
    "only ever INSERT into — never UPDATE or DELETE."
)
