"""Finite-report scope identification, not estimation of physical waste flows.

Use code exclusions, explicit description and recovery-stage evidence to bound
eligible input mass *within published rows*. Reporter totals are separate
universes. Bounds are not error bars or a complete national/EU physical supply.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
import pdfplumber

EXCLUDED = {"160601": "lead", "160602": "nickel-cadmium", "160603": "mercury"}
ROUTES = {"NL", "BE"}

def number(value: str | None) -> float:
    if value is None or not value.strip():
        raise ValueError("Missing quantity cannot be silently converted to zero")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invalid quantity: {value}")
    return result

def basel_pilot(path: Path, year: int = 2023) -> list[dict]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    records = []
    for text in soup.find_all(string=lambda x: x and x.strip() == "A1170"):
        cells = [x.get_text(" ", strip=True) for x in text.find_parent("tr").find_all("td", recursive=False)]
        if len(cells) != 11:
            raise ValueError("Unexpected Basel Table 5 schema")
        if cells[8] not in ROUTES:
            continue
        records.append({"origin": cells[8], "destination": "DE", "year": year,
                        "basel_code": cells[1], "y_code": cells[2], "low_code": cells[3],
                        "description": cells[4], "hazard_code": cells[5], "quantity_t": number(cells[6]),
                        "transit": cells[7], "d_code": cells[9], "r_code": cells[10],
                        "source": f"Basel Germany national report Table 5, {year}",
                        "evidence_grade": "administrative_report_not_independent_physical_reference"})
    if not records or not all(any(r["origin"] == origin for r in records) for origin in ROUTES):
        raise ValueError("Missing a fixed pilot route")
    return records

def uba_pilot(path: Path, year: int = 2023) -> list[dict]:
    country = {"Niederlande": "NL", "Belgien": "BE"}
    records = []
    with pdfplumber.open(path) as document:
        for index, page in enumerate(document.pages, 1):
            for line in (page.extract_text() or "").splitlines():
                match = re.fullmatch(r"(\d{6})\*?\s+(.+?)\s+(A\d{4})\s+(Niederlande|Belgien)\s+(R\d+|D\d+)\s+(.+?)\s+(\d+)", line)
                if match and (match[1].startswith("16060") or match[1] == "200133"):
                    records.append({"origin": country[match[4]], "destination": "DE", "year": year,
                                    "low_code": match[1], "description": match[2], "basel_code": match[3],
                                    "r_code": match[5], "quantity_t": number(match[7]), "page": index,
                                    "raw_line": line, "evidence_grade": "national_administrative_report"})
    if year == 2023 and len(records) != 10:
        raise ValueError(f"Pilot schema/coverage changed: expected ten printed rows, got {len(records)}")
    return records

def eligibility(row: dict, target: str, stage: str) -> tuple[float, float, str]:
    """Bounds for a row's share qualifying for a specified report-label task.

    Lithium means explicitly lithium-labelled (not Li-ion or EV). Unknown
    descriptions can contain that target; code-defined Pb/Cd/Hg cannot. R4 is
    a reported metal recovery operation, not measured recovered output.
    """
    if target not in {"lithium_family", "EV"} or stage not in {"all", "R4"}:
        raise ValueError("Unknown target/stage")
    if row["low_code"] in EXCLUDED:
        return 0., 0., "excluded_known_chemistry"
    if stage == "R4" and (row.get("r_code") != "R4" or row.get("d_code")):
        return 0., 0., "not_reported_R4"
    description = row.get("description", "").casefold()
    if target == "lithium_family" and description == "lithium batteries":
        return 1., 1., "explicit_reported_lithium_description"
    return 0., 1., "application_or_chemistry_unresolved"

def bounds(rows: list[dict], target: str, stage: str) -> dict:
    lower = upper = 0.
    for row in rows:
        low, high, _ = eligibility(row, target, stage)
        lower += low * row["quantity_t"]
        upper += high * row["quantity_t"]
    return {"lower_t": lower, "upper_t": upper, "width_t": upper - lower}

def ranking(a: dict, b: dict) -> str:
    if a["lower_t"] > b["upper_t"]:
        return "NL_strictly_above_BE_in_report_conditioned_set"
    if b["lower_t"] > a["upper_t"]:
        return "BE_strictly_above_NL_in_report_conditioned_set"
    return "not_identified"

def write_csv(path: Path, rows: list[dict]):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

def run(basel: Path, uba: Path, comext: Path, output: Path, year: int = 2023):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite prior analysis: {output}")
    output.mkdir(parents=True)
    b_rows, u_rows = basel_pilot(basel, year), uba_pilot(uba, year)
    # Basel and UBA share a national reporting basis. This is concordance only.
    concordance = []
    for printed in u_rows:
        if printed["basel_code"] != "A1170":
            continue
        fine = sum(r["quantity_t"] for r in b_rows if (r["origin"], r["low_code"], r["r_code"]) == (printed["origin"], printed["low_code"], printed["r_code"]))
        difference = abs(printed["quantity_t"] - fine)
        concordance.append({"origin": printed["origin"], "low_code": printed["low_code"], "r_code": printed["r_code"],
                            "uba_printed_t": printed["quantity_t"], "basel_reported_t": fine,
                            "absolute_difference_t": difference, "within_one_tonne": difference <= 1})
    if (year == 2023 and len(concordance) != 7) or not concordance or not all(r["within_one_tonne"] for r in concordance):
        raise ValueError("Administrative-source concordance failed; do not silently pool")
    by_route = {origin: [r for r in b_rows if r["origin"] == origin] for origin in sorted(ROUTES)}
    result = []
    rank_rows = []
    for target in ["lithium_family", "EV"]:
        for stage in ["all", "R4"]:
            b = {origin: bounds(rows, target, stage) for origin, rows in by_route.items()}
            for origin, interval in b.items():
                gross = sum(r["quantity_t"] for r in by_route[origin])
                result.append({"origin": origin, "destination": "DE", "year": year, "target": target,
                               "stage": stage, **interval, "unfiltered_A1170_t": gross,
                               "upper_reduction_percent": 100 * (gross - interval["upper_t"]) / gross,
                               "width_reduction_percent_vs_0_gross": 100 * (gross - interval["width_t"]) / gross,
                               "bound_type": "finite_report_conditional_not_physical_supply"})
            rank_rows.append({"target": target, "stage": stage, "ranking": ranking(b["NL"], b["BE"]),
                              "NL_lower_t": b["NL"]["lower_t"], "BE_upper_t": b["BE"]["upper_t"],
                              "strict_dominance_margin_t": b["NL"]["lower_t"] - b["BE"]["upper_t"]})
    with comext.open(encoding="utf-8-sig", newline="") as stream:
        c_rows = [r for r in csv.DictReader(stream) if r["year"] == str(year) and r["destination"] == "DE" and r["origin"] in ROUTES]
    inputs = []
    for origin in sorted(ROUTES):
        for scope in ["six_CN8", "spent_accumulators_only"]:
            observed = [r for r in c_rows if r["origin"] == origin and (scope == "six_CN8" or r["product"].endswith("20"))]
            totals = {v: sum(number(r["quantity_t"]) for r in observed if r["flow"] == v) for v in ["export", "import"]}
            counts = {v: sum(r["flow"] == v for r in observed) for v in totals}
            # An empty import series is unavailable, not a point-zero lower/upper.
            for view in ["export", "import"]:
                inputs.append({"origin": origin, "scope": scope, "view": view,
                               "reported_t": totals[view] if counts[view] else None,
                               "records": counts[view], "availability": "observed" if counts[view] else "unavailable_not_zero",
                               "target_lithium_share_lower": 0, "target_lithium_share_upper": 1,
                               "EV_specific": False, "reported_R4_identified": False})
    comparison = []
    for origin in sorted(ROUTES):
        for stage in ["all", "R4"]:
            known = bounds(by_route[origin], "lithium_family", stage)["lower_t"]
            for row in inputs:
                if row["origin"] != origin or row["reported_t"] is None:
                    continue
                feasible = known <= row["reported_t"] + 1e-10
                comparison.append({"origin": origin, "CN_scope": row["scope"], "view": row["view"], "stage": stage,
                                   "hypothetical_CN_upper_t": row["reported_t"], "Basel_report_label_lower_t": known,
                                   "same_population_and_exact_counting_assumption_feasible": feasible,
                                   "gap_if_infeasible_t": max(0, known - row["reported_t"]),
                                   "interpretation": "falsifies_naive_joint_exact_mapping_not_either_report_accuracy"})
    audit = {"pilot_year": year, "routes": ["BE-DE", "NL-DE"], "Basel_A1170_rows": len(b_rows),
             "UBA_battery_rows": len(u_rows), "administrative_concordance_groups": len(concordance),
             "independent_physical_reference": False, "source_redistribution": "No Basel raw or reconstructed row extract redistributed; local computations and limited factual case summaries only. UBA data reuse acknowledges source and alterations.",
             "EV_supply_accuracy_claim": "frozen_not_identified", "not_a_probability_interval": True,
             "hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [basel, uba, comext]}}
    # Small derived case summaries are not a released copy of the Basel database.
    write_csv(output / "uba_pilot_rows.csv", u_rows)
    write_csv(output / "administrative_concordance.csv", concordance)
    write_csv(output / "finite_report_scope_bounds.csv", result)
    write_csv(output / "route_rank_identification.csv", rank_rows)
    write_csv(output / "comext_pilot_inputs.csv", inputs)
    write_csv(output / "naive_scope_mapping_feasibility.csv", comparison)
    (output / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"audit": audit, "bounds": result, "ranks": rank_rows}, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--basel", type=Path, required=True)
    parser.add_argument("--uba", type=Path, required=True)
    parser.add_argument("--comext", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2023)
    args = parser.parse_args()
    run(args.basel, args.uba, args.comext, args.output, args.year)
