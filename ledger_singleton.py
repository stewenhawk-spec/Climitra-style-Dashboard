"""
ledger_singleton.py — one shared HashChainLedger instance for the whole app.

WHY THIS FILE EXISTS:
project_store.py and client_registry.py deliberately live in st.session_state
because that data is per-browser-tab and fine to lose on refresh. The ledger
is the opposite: it must be the SAME file, appended to in the SAME order, by
every user and every rerun — session_state would silently give each browser
tab its own disconnected ledger, which defeats the entire point.

st.cache_resource gives us one HashChainLedger object shared by every session
on this server process, backed by one file on disk.

DEPLOYMENT NOTE (read before you rely on this in production):
Streamlit Community Cloud's filesystem is NOT guaranteed persistent across
redeploys/restarts. For the prototype/local stage this is fine. Before you
hand ledger data to a VVB, back the ledger file with a persistent volume,
or add a periodic export step (mirroring the Export/Import pattern already
used in client_registry.py + views/settings.py) that pushes the .jsonl file
to a private git repo or a dedicated Google Sheet tab. A tampered-with ledger
you can't produce again on demand isn't audit-proof.
"""

import streamlit as st

from tamper_evident_ledger import HashChainLedger

LEDGER_PATH = "ledger/dmrv_ledger.jsonl"
KEY_PATH = "ledger/signing_key.pem"


@st.cache_resource
def get_ledger() -> HashChainLedger:
    return HashChainLedger(ledger_path=LEDGER_PATH, key_path=KEY_PATH)
