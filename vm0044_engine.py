"""
VM0044 Biochar dMRV Calculation Engine — Multi-Project Edition
================================================================
Implements Verra VM0044 v1.0/v1.1 "Methodology for Biochar Utilization in
Soil and Non-Soil Applications" — Low Technology Production Facility pathway
(Option P.2).

CHANGES FROM THE SINGLE-PROJECT VERSION:
  - All methodology constants and lookup tables moved to
    config/vm0044_defaults.yaml. Every function now takes a `config` dict
    instead of reading module-level constants, and any project can override
    values (a new feedstock's FCp, a measured local grid EF, etc.) without
    touching this file. The underlying equations are unchanged.
  - New check_satellite_sourcing() cross-checks delivered feedstock weight
    against the GEE/satellite biomass estimate for its source plot
    (Biomass_Sourcing_GEE tab), producing over-harvest and low-confidence
    flags independent of the batch-level QA checks below.
  - New run_project() is the single entry point for the dashboard/API layer:
    project_id + a data bundle in, full result package out.

Reads five input tables (mirroring the Google Sheet template):
  1. feedstock_df    - Suppliers & Feedstocks tab
  2. pyrolysis_df     - Pyrolysis Batches tab
  3. lab_df           - Lab_Data tab
  4. application_df   - Soil Application tab
  5. biomass_df       - Biomass_Sourcing_GEE tab (optional; enables satellite QA)

Author: dMRV build for Prani's biochar carbon project
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "vm0044_defaults.yaml"


# ---------------------------------------------------------------------------
# CONFIG LOADING
# ---------------------------------------------------------------------------

def load_config(overrides: dict = None, config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads the base VM0044 default config and deep-merges any project-specific
    overrides on top. `overrides` uses the same nested shape as the YAML
    file — you only need to specify the keys you're changing.

    Example override for a project with a measured local grid factor and a
    new feedstock category:
        {
            "emission_factors": {"grid_ef_kgco2_per_kwh": 0.65},
            "fixed_carbon_defaults": {"bamboo": {"pyrolysis": 0.71}},
        }
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)
    if overrides:
        config = _deep_merge(config, overrides)
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# CORE EQUATION FUNCTIONS (config-driven; math unchanged from v1)
# ---------------------------------------------------------------------------

def get_permanence_factor(tech_level: str, tprod_c: float, config: dict) -> float:
    """Equation 2/6 input: PRde,k"""
    pf = config["permanence_factor"]
    if tech_level == "low" or tprod_c is None or (isinstance(tprod_c, float) and pd.isna(tprod_c)):
        return pf["low_tech_default"]
    for lo, hi, val in pf["high_tech_bands"]:
        if lo <= tprod_c < hi:
            return val
    return pf["low_tech_default"]


def get_fixed_carbon(feedstock_category: str, process: str, config: dict, lab_fc: float = None) -> float:
    """
    Equation 2/6 input: FCp. Prefers lab-measured value (required annually /
    on feedstock change per Section 9.2); falls back to the config default table.
    """
    if lab_fc is not None and not pd.isna(lab_fc):
        return lab_fc
    fc_table = config["fixed_carbon_defaults"]
    try:
        return fc_table[feedstock_category][process]
    except KeyError:
        raise ValueError(
            f"No default FCp for feedstock='{feedstock_category}', process='{process}'. "
            f"Supply lab_fc for this batch, or add this feedstock to "
            f"config['fixed_carbon_defaults'] (via a project override or the YAML file)."
        )


def check_soil_eligibility(h_corg: float, config: dict) -> bool:
    """Applicability Condition 10b: H:Corg must be below threshold for soil application."""
    threshold = config["constants"]["h_corg_eligibility_threshold"]
    if h_corg is None or pd.isna(h_corg):
        return False  # cannot confirm eligibility without lab data -> not creditable yet
    return h_corg < threshold


def methane_project_emissions(dry_biochar_mass_t: float, config: dict, fe: float = None) -> float:
    """Equation 9 (low-tech PE_P,p,y): CH4 emissions from pyrolysis, low-tech facility. Returns tCO2e."""
    c = config["constants"]
    fe = fe if fe is not None else c["fe_default_low_tech"]
    return fe * c["gwp_ch4"] * dry_biochar_mass_t


def transport_leakage(distance_km_one_way: float, tonnes: float, config: dict) -> float:
    """Simplified CDM Tool 12 proxy. Only counted if one-way distance exceeds the config threshold. Returns tCO2e."""
    c = config["constants"]
    ef = config["emission_factors"]
    if distance_km_one_way is None or pd.isna(distance_km_one_way) or distance_km_one_way <= c["transport_leakage_threshold_km"]:
        return 0.0
    round_trip_km = distance_km_one_way * 2
    return (tonnes * round_trip_km * ef["transport_ef_kgco2_per_tkm"]) / 1000


def energy_emissions(fuel_liters: float, electricity_kwh: float, config: dict) -> float:
    """PE_D / PE_C components — fossil fuel + grid electricity emissions. Returns tCO2e."""
    ef = config["emission_factors"]
    co2_kg = (fuel_liters * ef["diesel_ef_kgco2_per_l"]) + (electricity_kwh * ef["grid_ef_kgco2_per_kwh"])
    return co2_kg / 1000


# ---------------------------------------------------------------------------
# BATCH-LEVEL CALCULATION
# ---------------------------------------------------------------------------

def compute_batch(row: dict, config: dict) -> dict:
    """
    row must contain:
      batch_id, tech_level ('low'/'high'), feedstock_category, process ('pyrolysis'/'gasification'),
      biochar_output_wet_kg, moisture_pct, ash_pct,
      lab_fc (None if unavailable), h_corg, tprod_c (None if unmeasured),
      diesel_l, electricity_kwh, transport_km_one_way
    Returns dict with full calculation trace.
    """
    out = dict(row)
    c = config["constants"]

    # 1. Dry, ash-corrected biochar mass (tonnes)
    dry_mass_t = (row["biochar_output_wet_kg"] *
                  (1 - row["moisture_pct"] - row["ash_pct"])) / 1000
    out["dry_biochar_mass_t"] = round(dry_mass_t, 4)

    # 2. Eligibility gate
    eligible = check_soil_eligibility(row.get("h_corg"), config)
    out["soil_eligible"] = eligible

    if not eligible:
        out["net_tCO2e"] = 0.0
        out["flag"] = "INELIGIBLE: H:Corg missing or over threshold"
        return out

    # 3. Fixed carbon fraction (lab value preferred, else config default)
    try:
        fc = get_fixed_carbon(row["feedstock_category"], row["process"], config, row.get("lab_fc"))
    except ValueError as e:
        out["net_tCO2e"] = 0.0
        out["flag"] = f"MISSING FCp: {e}"
        return out
    out["fc_used"] = fc

    # 4. Permanence factor
    pr = get_permanence_factor(row["tech_level"], row.get("tprod_c"), config)
    out["pr_de_k_used"] = pr

    # 5. Organic carbon content stored (Equation 2/6) -> CO2e removed
    cc_t = dry_mass_t * fc * pr
    co2e_removed = cc_t * c["co2_per_c"]
    out["carbon_stock_t"] = round(cc_t, 4)
    out["co2e_removed_gross"] = round(co2e_removed, 4)

    # 6. Project emissions - production stage
    pe_energy = energy_emissions(row.get("diesel_l", 0) or 0, row.get("electricity_kwh", 0) or 0, config)
    pe_methane = methane_project_emissions(dry_mass_t, config) if row["tech_level"] == "low" else 0.0
    pe_production = pe_energy + pe_methane
    out["pe_energy_tCO2e"] = round(pe_energy, 4)
    out["pe_methane_tCO2e"] = round(pe_methane, 4)

    # 7. Leakage - transport (only if beyond configured threshold)
    le_transport = transport_leakage(row.get("transport_km_one_way", 0), dry_mass_t, config)
    out["leakage_transport_tCO2e"] = round(le_transport, 4)

    # 8. Net removal
    net = co2e_removed - pe_production - le_transport
    out["net_tCO2e"] = round(net, 4)
    out["flag"] = "OK"
    return out


# ---------------------------------------------------------------------------
# SATELLITE / GEE SOURCING CROSS-CHECK
# ---------------------------------------------------------------------------

def check_satellite_sourcing(feedstock_df: pd.DataFrame, biomass_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Cross-checks each feedstock delivery against the satellite-derived
    biomass estimate for its source plot (Biomass_Sourcing_GEE tab), joined
    on gee_plot_id. Independent of the batch-level QA in run_pipeline() —
    this operates upstream, at the sourcing/delivery level, before feedstock
    ever reaches the kiln.

    Expects:
      feedstock_df: gee_plot_id, feedstock_id, weight_delivered_kg
      biomass_df:   gee_plot_id, est_total_biomass_t, classification_confidence_pct

    Returns two flags per delivery:
      - over_harvest_flag: delivered weight exceeds the plot's estimated
        available biomass beyond the configured tolerance
      - low_confidence_flag: the AI classification confidence for that plot
        is below the configured threshold, so the estimate itself is weak
    """
    qa = config["satellite_qa"]
    merged = feedstock_df.merge(biomass_df, on="gee_plot_id", how="left", suffixes=("", "_plot"))

    merged["weight_delivered_t"] = merged["weight_delivered_kg"] / 1000
    tolerance = 1 + (qa["over_harvest_tolerance_pct"] / 100)

    merged["over_harvest_flag"] = np.where(
        merged["est_total_biomass_t"].isna(), "NO PLOT DATA",
        np.where(
            merged["weight_delivered_t"] > merged["est_total_biomass_t"] * tolerance,
            "OVER-HARVEST", "OK"
        )
    )
    merged["low_confidence_flag"] = np.where(
        merged["classification_confidence_pct"] < qa["min_classification_confidence_pct"],
        "LOW CONFIDENCE", "OK"
    )

    return merged[[
        "feedstock_id", "gee_plot_id", "weight_delivered_t", "est_total_biomass_t",
        "over_harvest_flag", "classification_confidence_pct", "low_confidence_flag"
    ]]


# ---------------------------------------------------------------------------
# PROJECT-LEVEL PIPELINE
# ---------------------------------------------------------------------------

def run_pipeline(feedstock_df, pyrolysis_df, lab_df, application_df, config: dict) -> dict:
    """
    Joins the batch-level tabs, runs compute_batch() per row, and produces:
      - batch_ledger (DataFrame)
      - project_summary (dict)
      - qa_flags (DataFrame)
    """
    merged = pyrolysis_df.merge(lab_df, on="batch_id", how="left", suffixes=("", "_lab"))

    results = [compute_batch(row, config) for row in merged.to_dict("records")]
    ledger = pd.DataFrame(results)

    # QA CHECK 1: applied mass vs produced mass, per batch
    applied_sum = application_df.groupby("linked_batch_id")["applied_weight_kg"].sum()
    ledger["dry_mass_kg"] = ledger["dry_biochar_mass_t"] * 1000
    ledger = ledger.merge(applied_sum.rename("total_applied_kg"),
                           left_on="batch_id", right_index=True, how="left")
    ledger["total_applied_kg"] = ledger["total_applied_kg"].fillna(0)
    ledger["mass_balance_flag"] = np.where(
        ledger["total_applied_kg"] > ledger["dry_mass_kg"] * 1.01,  # 1% tolerance
        "OVER-ALLOCATED", "OK"
    )

    # QA CHECK 2: missing lab data
    ledger["lab_data_flag"] = np.where(ledger["h_corg"].isna(), "MISSING LAB DATA", "OK")

    project_summary = {
        "total_batches": len(ledger),
        "eligible_batches": int((ledger["soil_eligible"] == True).sum()),
        "ineligible_batches": int((ledger["soil_eligible"] == False).sum()),
        "gross_co2e_removed": round(ledger["co2e_removed_gross"].sum(), 3),
        "total_project_emissions": round((ledger["pe_energy_tCO2e"].sum() +
                                           ledger["pe_methane_tCO2e"].sum()), 3),
        "total_leakage": round(ledger["leakage_transport_tCO2e"].sum(), 3),
        "net_tCO2e_project": round(ledger["net_tCO2e"].sum(), 3),
        "batches_flagged_mass_balance": int((ledger["mass_balance_flag"] == "OVER-ALLOCATED").sum()),
        "batches_flagged_missing_lab": int((ledger["lab_data_flag"] == "MISSING LAB DATA").sum()),
    }

    qa_flags = ledger[(ledger["flag"] != "OK") |
                       (ledger["mass_balance_flag"] != "OK") |
                       (ledger["lab_data_flag"] != "OK")][
        ["batch_id", "flag", "mass_balance_flag", "lab_data_flag"]
    ]

    return {"ledger": ledger, "summary": project_summary, "qa_flags": qa_flags}


def run_project(project_id: str, feedstock_df, pyrolysis_df, lab_df, application_df,
                 biomass_df: pd.DataFrame = None, config_overrides: dict = None) -> dict:
    """
    Single entry point for the dashboard/API layer. Runs the full VM0044
    pipeline for one project's data bundle and returns everything the
    dashboard needs to render.

    Pass config_overrides to customize methodology parameters for this
    project only (new feedstock FCp, local grid EF, etc.) without touching
    the shared default config.

    Returns:
      {
        "project_id": str,
        "ledger": DataFrame,               # per-batch calc trace
        "summary": dict,                   # project-level rollup
        "qa_flags": DataFrame,              # batch-level flags
        "satellite_sourcing_qa": DataFrame  # only present if biomass_df supplied
      }
    """
    config = load_config(config_overrides)

    result = run_pipeline(feedstock_df, pyrolysis_df, lab_df, application_df, config)
    result["project_id"] = project_id

    if biomass_df is not None:
        result["satellite_sourcing_qa"] = check_satellite_sourcing(feedstock_df, biomass_df, config)

    return result
