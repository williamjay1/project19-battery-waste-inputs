"""Temporal holdout of descriptive information priorities; not facility prediction."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from src.comext_decision_input_analysis import EU27, RULES, SPENT, priority_sets, reported_shares
from src.comext_network_quality_analysis import read_csv, write_csv


def coverage(shares: dict, selected: tuple[str, ...]) -> tuple[float, float, float]:
    e, i = (sum(shares[rule].get((c,), 0.0) for c in selected) for rule in RULES[:2])
    return e, i, min(e, i)


def evaluate(rows: list[dict], k_values=range(1, 6)) -> list[dict]:
    train = [r for r in rows if 2022 <= int(r["year"]) <= 2024]
    held = [r for r in rows if int(r["year"]) == 2025]
    train_shares = {r: reported_shares(train, r, ("destination",)) for r in RULES}
    held_shares = {r: reported_shares(held, r, ("destination",)) for r in RULES}
    if any(not s for s in (*train_shares.values(), *held_shares.values())):
        raise ValueError("Both reporter distributions are required in both windows")
    results = []
    for k in k_values:
        reference = [coverage(held_shares, cs)[2] for cs in itertools.combinations(EU27, k)]
        for selection in priority_sets(train_shares, k):
            selected = tuple(selection["selected_destination_countries"].split(";"))
            e, i, worst = coverage(held_shares, selected)
            results.append({**selection, "selection_window": "2022-2024", "evaluation_window": "2025",
                            "heldout_exporter_coverage": e, "heldout_importer_coverage": i,
                            "heldout_smaller_coverage": worst,
                            "uniform_country_set_expected_smaller_coverage": sum(reference) / len(reference),
                            "fraction_country_sets_with_smaller_coverage_at_most_selected":
                                sum(v <= worst + 1e-14 for v in reference) / len(reference),
                            "number_all_same_budget_country_sets": len(reference)})
    return results


def run(source: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    rows = read_csv(source)
    result = []
    for name, subset in (("all_six", rows), ("spent_accumulator_label", [r for r in rows if r["product"] in SPENT])):
        result.extend({"classification_group": name, **r} for r in evaluate(subset))
    output.mkdir(parents=True)
    write_csv(output / "temporal_holdout_information_coverage.csv", result)
    audit = {"source": str(source), "selection_window": "2022-2024", "holdout_window": "2025",
             "budgets": [1, 2, 3, 4, 5], "selection_rules": list(RULES) + ["minimax_two_reporter_views"],
             "holdout_used_for_selection": False, "preregistration": False,
             "reference": "Exact enumeration of uniformly weighted EU27 country sets at the same budget; no random-seed sampling.",
             "uncertainty": "Reference ranks are not confidence intervals or hypothesis-test p values.",
             "limitation": "One annual holdout, known only after exploratory selection of the research question; no physical-flow or future-outcome validation."}
    (output / "analysis_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output), indent=2))
