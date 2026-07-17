"""
views/report.py — Registry-format Monitoring Report (Verra / Puro.earth /
Isometric style), generated straight from a calculated project and the
tamper-evident audit ledger, so a VVB can verify the net emission reduction
claim without re-deriving anything by hand.

WHAT THIS PAGE DOES:
  1. Lets you pick a calculated project (from the Projects tab) and fill in
     the handful of fields a calculation run doesn't know on its own --
     monitoring period dates, report version, who prepared it.
  2. Shows an in-app preview of every section a VVB would expect: project
     description, ex-ante (fixed) parameters, ex-post (monitored) per-batch
     data, the GHG quantification results, QA/QC flags, and an audit-trail
     section pulled LIVE from the ledger (chain-verified on the spot when
     you open this page, not just asserted from a cached value).
  3. Renders the same content to a downloadable .docx via report_generator.py
     -- something you can actually hand to a VVB or upload to a registry
     portal.

WHAT THIS PAGE DOES NOT DO:
  It doesn't talk to Verra/Puro.earth/Isometric APIs, and it doesn't try to
  reproduce any one registry's exact official template pixel-for-pixel --
  those differ registry-to-registry and change over time. This produces a
  methodology-complete *evidence package* (every number a VVB needs, with a
  traceable, independently-verifiable audit trail) that you paste into
  whichever registry's official monitoring report template. Section 3 of
  the SKILL-adjacent report_generator.py is the place to edit if you need
  different section headings for a specific template.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from datetime import date

import pandas as pd
import streamlit as st

import project_store as store
from ledger_singleton import get_ledger
from vm0044_engine import load_config
from report_generator import build_docx_report

st.title("Monitoring Report")
st.caption(
    "A registry-format (Verra / Puro.earth / Isometric-style) monitoring report, "
    "built directly from a calculated project and the tamper-evident audit ledger "
    "-- every figure here traces back to a hash-chained, signed ledger entry a VVB "
    "can re-verify independently."
)

all_projects = store.get_all_projects()

if not all_projects:
    st.info(
        "No calculated projects yet. Go to the **Projects** tab, run a calculation, "
        "then come back here to generate its monitoring report."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Step 1: pick the project + fill in report-level metadata the calculation
# itself doesn't know (monitoring period, report version, preparer).
# ---------------------------------------------------------------------------
st.subheader("1. Report scope")

project_ids = list(all_projects.keys())
current = st.session_state.get("current_project")
default_index = project_ids.index(current) if current in project_ids else 0
selected_id = st.selectbox("Project", project_ids, index=default_index, key="report_project_select")

project = all_projects[selected_id]
result = project["result"]
ledger_df = result["ledger"]
summary = result["summary"]
meta = project["meta"]

rc1, rc2, rc3 = st.columns(3)
period_start = rc1.date_input("Monitoring period start", value=date(date.today().year, 1, 1), key="report_period_start")
period_end = rc2.date_input("Monitoring period end", value=date.today(), key="report_period_end")
report_version = rc3.text_input("Report version", value="1.0", key="report_version")

rc4, rc5 = st.columns(2)
prepared_by = rc4.text_input("Prepared by", value=st.session_state.get("user_name", ""), key="report_prepared_by")
methodology_version = rc5.text_input(
    "Methodology & version", value="VM0044 v1.1 — Low-Technology Production Facility (P.2)",
    key="report_methodology",
)

notes = st.text_area(
    "Additional notes for the VVB (optional)", key="report_notes",
    placeholder="e.g. deviations from the monitoring plan, prior verification history, contact for clarifications",
)

st.divider()

# ---------------------------------------------------------------------------
# Step 2: preview -- same sections that will go into the .docx
# ---------------------------------------------------------------------------
st.subheader("2. Project description")
desc_rows = {
    "Project ID": selected_id,
    "Project Name": meta.get("Project Name", "—"),
    "Registry": meta.get("Registry", "—"),
    "Methodology": methodology_version,
    "Facility Address": meta.get("Facility Address", "—"),
    "Facility Coordinates": f"{project['lat']:.4f}, {project['lon']:.4f}",
    "Pyrolysis Reactor(s)": meta.get("Pyrolysis Reactor(s)", "—"),
    "Project Start Date": meta.get("Project Start Date", "—"),
    "Project Supervisor": meta.get("Project Supervisor", "—"),
    "Monitoring Period": f"{period_start.isoformat()} to {period_end.isoformat()}",
}
st.table(pd.DataFrame(desc_rows.items(), columns=["Field", "Value"]).set_index("Field"))

effective_config = load_config(project.get("config_overrides"))

st.subheader("3. Data and parameters — fixed at validation (ex-ante)")
st.caption(
    "VM0044 default values, unless a project-specific override was supplied when "
    "this project was calculated (shown below the table if so)."
)
ante_rows = [
    ("CO2 per unit C (44/12)", effective_config["constants"]["co2_per_c"], "—", "Stoichiometric constant"),
    ("GWP of CH4 (AR5, 100yr)", effective_config["constants"]["gwp_ch4"], "—", "IPCC AR5, VM0044 Sec 9.1"),
    ("Default Fe, low-tech kiln", effective_config["constants"]["fe_default_low_tech"], "tCH4/t biochar", "Cornelissen et al. 2016"),
    ("H:Corg eligibility threshold", effective_config["constants"]["h_corg_eligibility_threshold"], "—", "Applicability Condition 10b"),
    ("Transport leakage distance threshold", effective_config["constants"]["transport_leakage_threshold_km"], "km one-way", "CDM Tool 16"),
    ("Diesel emission factor", effective_config["emission_factors"]["diesel_ef_kgco2_per_l"], "kgCO2/L", "IPCC standard"),
    ("Grid emission factor", effective_config["emission_factors"]["grid_ef_kgco2_per_kwh"], "kgCO2/kWh", "Project/country grid EF"),
    ("Transport emission factor", effective_config["emission_factors"]["transport_ef_kgco2_per_tkm"], "kgCO2/t-km", "CDM Tool 12 / local factor"),
    ("Permanence factor, low-tech default (PRde,k)", effective_config["permanence_factor"]["low_tech_default"], "—", "VM0044 Table 4"),
]
st.dataframe(pd.DataFrame(ante_rows, columns=["Parameter", "Value", "Unit", "Source"]),
             use_container_width=True, hide_index=True)

with st.expander("Fixed carbon defaults (FCp) by feedstock & process"):
    fc_rows = []
    for feed, procs in effective_config["fixed_carbon_defaults"].items():
        for proc, val in procs.items():
            fc_rows.append({"Feedstock category": feed, "Process": proc, "Default FCp": val})
    st.dataframe(pd.DataFrame(fc_rows), use_container_width=True, hide_index=True)

if project.get("config_overrides"):
    st.warning(f"Project-specific overrides applied to the defaults above: `{project['config_overrides']}`")

st.subheader("4. Data and parameters monitored (ex-post, per batch)")
monitored_cols = [c for c in [
    "batch_id", "feedstock_category", "process", "tech_level",
    "biochar_output_wet_kg", "moisture_pct", "ash_pct",
    "lab_fc", "fc_used", "h_corg", "tprod_c",
    "diesel_l", "electricity_kwh", "transport_km_one_way",
] if c in ledger_df.columns]
st.dataframe(ledger_df[monitored_cols], use_container_width=True, hide_index=True)

st.subheader("5. GHG emission reduction / removal quantification")
calc_cols = [c for c in [
    "batch_id", "dry_biochar_mass_t", "soil_eligible", "carbon_stock_t",
    "co2e_removed_gross", "pe_energy_tCO2e", "pe_methane_tCO2e",
    "leakage_transport_tCO2e", "net_tCO2e", "flag",
] if c in ledger_df.columns]
st.dataframe(ledger_df[calc_cols], use_container_width=True, hide_index=True)

s1, s2, s3, s4 = st.columns(4)
s1.metric("Gross CO2e removed", f"{summary['gross_co2e_removed']} t")
s2.metric("Project emissions", f"{summary['total_project_emissions']} t")
s3.metric("Leakage", f"{summary['total_leakage']} t")
s4.metric("Net tCO2e (this run)", f"{summary['net_tCO2e_project']} t")

st.subheader("6. QA/QC procedures & results")
qflag1, qflag2, qflag3 = st.columns(3)
qflag1.metric("Ineligible batches", summary["ineligible_batches"])
qflag2.metric("Mass-balance flags", summary["batches_flagged_mass_balance"])
qflag3.metric("Missing lab data flags", summary["batches_flagged_missing_lab"])

if len(result["qa_flags"]) == 0:
    st.success("No batch-level QA issues found in this run.")
else:
    st.dataframe(result["qa_flags"], use_container_width=True, hide_index=True)

if "satellite_sourcing_qa" in result:
    st.markdown("**Satellite sourcing cross-check (feedstock delivery vs. GEE biomass estimate)**")
    st.dataframe(result["satellite_sourcing_qa"], use_container_width=True, hide_index=True)

st.subheader("7. Audit trail (tamper-evident ledger)")
ledger = get_ledger()
chain_ok, issues = ledger.verify_chain()

trail_records = []
if ledger.ledger_path.exists():
    with open(ledger.ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d["record_id"] == selected_id or d["record_id"].startswith(f"{selected_id}:"):
                trail_records.append(d)

ac1, ac2 = st.columns(2)
with ac1:
    if chain_ok:
        st.success("Full ledger chain verified — no tampering detected.")
    else:
        st.error(f"Ledger chain INVALID — {len(issues)} issue(s) found.")
with ac2:
    st.metric(f"Ledger entries for {selected_id}", len(trail_records))

if trail_records:
    seqs = [r["seq"] for r in trail_records]
    st.caption(
        f"Sequence numbers {min(seqs)}–{max(seqs)} of the full chain. Download the full "
        f"ledger + public key on the **Audit Log** tab for independent verification."
    )
    st.dataframe(
        pd.DataFrame(trail_records)[["seq", "record_type", "record_id", "timestamp", "entry_hash"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.warning(f"No ledger entries found for `{selected_id}` yet — re-run the calculation on the Projects tab to commit one.")

st.divider()

# ---------------------------------------------------------------------------
# Step 3: generate + download the .docx
# ---------------------------------------------------------------------------
st.subheader("8. Generate report")
st.caption("Produces a .docx with every section above, formatted for handoff to a VVB or upload to a registry portal.")

if st.button("📄 Generate Monitoring Report (.docx)", type="primary"):
    report_meta = {
        "registry": meta.get("Registry", "—"),
        "methodology": methodology_version,
        "period_start": period_start,
        "period_end": period_end,
        "report_version": report_version,
        "prepared_by": prepared_by or "—",
        "report_date": date.today(),
        "notes": notes,
    }
    docx_bytes = build_docx_report(
        project_id=selected_id,
        project=project,
        config_effective=effective_config,
        report_meta=report_meta,
        chain_ok=chain_ok,
        chain_issues=issues,
        trail_records=trail_records,
        public_key_pem=ledger.export_public_key_pem(),
    )
    st.session_state["_generated_report_bytes"] = docx_bytes
    st.session_state["_generated_report_name"] = f"{selected_id}_monitoring_report_v{report_version}.docx"
    st.success("Report generated — download it below.")

if st.session_state.get("_generated_report_bytes"):
    st.download_button(
        "⬇️ Download Monitoring Report (.docx)",
        st.session_state["_generated_report_bytes"],
        file_name=st.session_state["_generated_report_name"],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
