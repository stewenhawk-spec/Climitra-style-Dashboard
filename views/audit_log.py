"""
views/audit_log.py — the real, append-only, tamper-evident audit trail.

Every batch committed on the Projects tab lands here as a hash-chained,
signed ledger entry. This page lets you:
  - see the full chain (newest first) with a one-click integrity check
  - drill into a single batch's full history
  - export the public key + ledger file for a VVB/auditor to verify
    independently, without trusting this app's server
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import pandas as pd
import streamlit as st

from ledger_singleton import get_ledger

st.title("Audit Log")

ledger = get_ledger()

if not ledger.ledger_path.exists() or ledger.ledger_path.stat().st_size == 0:
    st.info(
        "No ledger entries yet. Run a calculation on the **Projects** tab — every "
        "batch and project run is committed here automatically, hash-chained and "
        "signed. Nothing here can be edited after the fact without breaking the chain."
    )
    st.stop()

# --- Integrity check ---------------------------------------------------
ok, issues = ledger.verify_chain()

c1, c2 = st.columns([1, 3])
with c1:
    if ok:
        st.success("Chain verified — no tampering detected")
    else:
        st.error(f"CHAIN INVALID — {len(issues)} issue(s) found")
with c2:
    if not ok:
        with st.expander("See what's wrong", expanded=True):
            for i in issues:
                st.write(f"- {i}")

st.caption(
    "This check re-walks every entry: recomputes each hash, confirms it links to "
    "the previous entry, and verifies the Ed25519 signature. A single edited "
    "byte anywhere in the ledger file fails this check."
)

st.divider()

# --- Load all entries ----------------------------------------------------
entries = []
with open(ledger.ledger_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            entries.append(json.loads(line))

df = pd.DataFrame(entries)

# --- Filters -------------------------------------------------------------
fc1, fc2 = st.columns(2)
type_filter = fc1.multiselect(
    "Record type", options=sorted(df["record_type"].unique()),
    default=sorted(df["record_type"].unique()),
)
search = fc2.text_input("Search record ID", placeholder="e.g. PROJ-DELHI-001 or a batch_id")

filtered = df[df["record_type"].isin(type_filter)]
if search:
    filtered = filtered[filtered["record_id"].str.contains(search, case=False, na=False)]

st.subheader(f"Ledger entries ({len(filtered)} of {len(df)})")
st.dataframe(
    filtered[["seq", "record_type", "record_id", "timestamp", "data_hash", "prev_hash"]]
    .sort_values("seq", ascending=False),
    use_container_width=True,
    height=360,
)

st.divider()

# --- Drill into one record's full history --------------------------------
st.subheader("Trace a single record")
record_id = st.text_input(
    "Record ID (e.g. PROJ-DELHI-001:BATCH-2026-001)",
    key="audit_trace_id",
    help="Project-level runs are logged under the Project ID; batches are logged as "
         "PROJECT_ID:BATCH_ID so the same batch_id used across two clients doesn't collide.",
)
if record_id:
    trail = ledger.get_audit_trail(record_id)
    if not trail:
        st.warning(f"No ledger entries found for `{record_id}`.")
    else:
        for entry in trail:
            with st.expander(f"seq {entry['seq']} — {entry['timestamp']}"):
                st.json(entry)

st.divider()

# --- Export for independent verification ----------------------------------
st.subheader("Share with a verifier (VVB)")
st.caption(
    "Give a VVB or auditor the public key and the ledger file. They can "
    "independently recompute every hash and check every signature without "
    "needing access to this app or trusting this server."
)
ec1, ec2 = st.columns(2)
with ec1:
    st.download_button(
        "⬇️ Download ledger (.jsonl)",
        ledger.ledger_path.read_text(),
        file_name="dmrv_ledger.jsonl",
    )
with ec2:
    st.download_button(
        "⬇️ Download public key (.pem)",
        ledger.export_public_key_pem(),
        file_name="dmrv_ledger_public_key.pem",
    )
