"""Declaration-coverage and asymmetry diagnostics of fixed country priorities.

Outcome diagnostics never select countries. Unknown quantities stay unknown;
undefined asymmetry and denominator shares are explicit missing values. These
are declaration comparisons, not validation against physical movements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from src.comext_decision_input_analysis import RULES, SPENT, priority_sets, reported_shares
from src.comext_network_quality_analysis import read_csv, write_csv


def quantity(value):
    if value is None or str(value).strip() == "":
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invalid declared quantity: {value!r}")
    return result


def diagnostics(rows, selected):
    subset = [r for r in rows if r["destination"] in selected]
    pairs, country_asymmetries = [], defaultdict(list)
    e_total = i_total = matched_e = matched_i = difference = pair_sum = 0.0
    matched = positive_both = zero_sum = unmatched = 0
    for row in subset:
        e, i = quantity(row["export_mass_t"]), quantity(row["import_mirror_mass_t"])
        if e is not None:
            e_total += e
        if i is not None:
            i_total += i
        if e is None or i is None:
            unmatched += 1
            continue
        matched += 1
        matched_e += e
        matched_i += i
        positive_both += int(e > 0 and i > 0)
        if e + i == 0:
            zero_sum += 1
            continue
        asymmetry = 200 * abs(e - i) / (e + i)
        pairs.append(asymmetry)
        country_asymmetries[row["destination"]].append(asymmetry)
        difference += abs(e - i)
        pair_sum += e + i
    country_means = [sum(v) / len(v) for v in country_asymmetries.values()]
    return {
        "selected_union_keys": len(subset), "matched_quantity_keys": matched,
        "matched_positive_sum_keys": len(pairs), "matched_both_positive_keys": positive_both,
        "matched_zero_sum_keys": zero_sum, "unmatched_quantity_keys": unmatched,
        "exporter_available_mass_t": e_total, "importer_available_mass_t": i_total,
        "matched_exporter_mass_share": matched_e / e_total if e_total else None,
        "matched_importer_mass_share": matched_i / i_total if i_total else None,
        "mean_record_asymmetry_percent": sum(pairs) / len(pairs) if pairs else None,
        "equal_country_mean_asymmetry_percent": sum(country_means) / len(country_means) if country_means else None,
        "countries_with_defined_asymmetry": len(country_means),
        "weighted_asymmetry_percent": 200 * difference / pair_sum if pair_sum else None,
        "paired_absolute_difference_t": difference if pairs else None,
        "asymmetry_quality_flag": "paired_declarations_only" if pairs else "undefined_no_positive_sum_pair",
        "coverage_quality_flag": "defined_both_totals" if e_total and i_total else "missing_or_zero_view_total",
    }


def run(input_dir: Path, output_dir: Path):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    input_path = input_dir / "eu27_mirror_comparison.csv"
    rows = read_csv(input_path)
    for row in rows:
        row["year"] = int(row["year"])
        for field in ("export_mass_t", "import_mirror_mass_t"):
            row[field] = quantity(row[field])
    results, whole_population = [], []
    for scope, scoped in (("all_six", rows), ("spent_accumulator_label", [r for r in rows if r["product"] in SPENT])):
        for selection_window, evaluation_window, training, evaluation in (
            ("2022-2025", "2022-2025", scoped, scoped),
            ("2022-2024", "2025", [r for r in scoped if r["year"] <= 2024], [r for r in scoped if r["year"] == 2025]),
        ):
            shares = {rule: reported_shares(training, rule, ("destination",)) for rule in RULES}
            eval_shares = {rule: reported_shares(evaluation, rule, ("destination",)) for rule in RULES[:2]}
            whole_population.append({"scope": scope, "evaluation_window": evaluation_window,
                                     **diagnostics(evaluation, {r["destination"] for r in evaluation})})
            for k in range(1, 6):
                for choice in priority_sets(shares, k):
                    selected = choice["selected_destination_countries"].split(";")
                    coverage = {rule: sum(eval_shares[rule].get((c,), 0) for c in selected) for rule in RULES[:2]}
                    results.append({"scope": scope, "selection_window": selection_window,
                        "evaluation_window": evaluation_window,
                        "country_budget_k": k, "selection_rule": choice["selection_rule"],
                        "selected_countries": ";".join(selected),
                        "exporter_coverage": coverage["exporter"],
                        "importer_coverage": coverage["importer_mirror"],
                        "smaller_view_coverage": min(coverage.values()),
                        **diagnostics(evaluation, set(selected))})
    output_dir.mkdir(parents=True)
    write_csv(output_dir / "priority_quality_diagnostics.csv", results)
    write_csv(output_dir / "population_quality_diagnostics.csv", whole_population)
    audit = {"input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
             "selection_rows": len(results), "country_budgets": [1, 2, 3, 4, 5],
             "scopes": ["all_six", "spent_accumulator_label"],
             "design": "Full-window retrospective and fixed 2022-2024 selection evaluated on 2025; all four rules retained.",
             "selection_uses_quality_outcomes": False,
             "missing_policy": "No unknown quantity is zero-filled; zero-sum pairs have undefined asymmetry; undefined results are blank with flags.",
             "interpretation": "Coverage and paired-declaration asymmetry are distinct; neither is verified physical accuracy or a realised information gain."}
    (output_dir / "audit_summary.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)
