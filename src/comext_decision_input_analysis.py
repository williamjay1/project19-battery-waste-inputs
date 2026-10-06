"""Decision-input diagnostics of public declarations, not physical-flow estimates.

No capacity, cost, facility, EV chemistry or missing shipment is invented.
Country selection is a small-budget information-priority exercise: it maximises
the share of published destination-associated mass represented by selected
countries. It must never be interpreted as optimal recycling-facility siting.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import defaultdict
from pathlib import Path

from src.comext_network_quality_analysis import number, read_csv, write_csv

EU27 = tuple(sorted({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
    "RO", "SK", "SI", "ES", "SE",
}))
RULES = ("exporter", "importer_mirror", "available_max")
SPENT = {"85491320", "85491420", "85491920"}


def report_value(row: dict, rule: str) -> float | None:
    e, i = number(row["export_mass_t"]), number(row["import_mirror_mass_t"])
    if rule == "exporter":
        return e
    if rule == "importer_mirror":
        return i
    if rule == "available_max":
        available = [v for v in (e, i) if v is not None]
        return max(available) if available else None
    raise ValueError(rule)


def reported_shares(rows: list[dict], rule: str, keys: tuple[str, ...]) -> dict:
    masses: dict[tuple, float] = defaultdict(float)
    for row in rows:
        value = report_value(row, rule)
        if value is not None and value > 0:
            masses[tuple(row[k] for k in keys)] += value
    total = sum(masses.values())
    return {k: v / total for k, v in masses.items()} if total else {}


def share_overlap(first: dict, second: dict) -> float | None:
    # Missing keys mean no positive contribution to the published-mass sum,
    # not a zero physical shipment. This is a distribution of available reports.
    if not first or not second:
        return None
    return sum(min(first.get(k, 0.0), second.get(k, 0.0)) for k in first.keys() | second.keys())


def support_overlap(rows: list[dict], keys: tuple[str, ...]) -> dict:
    e = set(reported_shares(rows, "exporter", keys))
    i = set(reported_shares(rows, "importer_mirror", keys))
    union = e | i
    return {
        "export_positive_reported_units": len(e),
        "import_positive_reported_units": len(i),
        "intersection_units": len(e & i),
        "union_units": len(union),
        "support_jaccard": len(e & i) / len(union) if union else None,
        "normalised_reported_mass_overlap": share_overlap(
            reported_shares(rows, "exporter", keys), reported_shares(rows, "importer_mirror", keys)
        ),
    }


def priority_sets(shares: dict[str, dict], k: int) -> list[dict]:
    if not 1 <= k <= len(EU27):
        raise ValueError("priority budget outside EU-27")
    choices: dict[str, tuple[str, ...]] = {}
    for rule in RULES:
        choices[rule] = tuple(sorted(EU27, key=lambda c: (-shares[rule].get((c,), 0.0), c))[:k])
    # The max view is derived from E and I, not an independent third source.
    # Minimax uses only the two original reporter views, each normalised by its
    # own published mass. All country combinations are exhaustively evaluated.
    best_score, best_set = -1.0, None
    for selected in itertools.combinations(EU27, k):
        score = min(sum(shares[r].get((c,), 0.0) for c in selected) for r in RULES[:2])
        if score > best_score + 1e-14:
            best_score, best_set = score, selected
    choices["minimax_two_reporter_views"] = best_set
    return [{
        "selection_rule": rule, "country_budget_k": k,
        "selected_destination_countries": ";".join(sorted(selected)),
        **{f"share_under_{r}": sum(shares[r].get((c,), 0.0) for c in selected) for r in RULES},
        "worst_share_under_two_reporter_views": min(sum(shares[r].get((c,), 0.0) for c in selected) for r in RULES[:2]),
        "interpretation": "Coverage of available declarations for information prioritisation; no facility-siting or physical-capacity claim.",
    } for rule, selected in choices.items()]


def run(input_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    rows = read_csv(input_dir / "eu27_mirror_comparison.csv")
    for row in rows:
        row["year"] = int(row["year"])
        for key in ("export_mass_t", "import_mirror_mass_t"):
            row[key] = number(row[key])
        if row["origin"] not in EU27 or row["destination"] not in EU27:
            raise ValueError("Non-EU27 row in main analysis")
        if row["origin"] == row["destination"]:
            raise ValueError("Domestic self route is outside the bilateral population")
        if any(row[k] is not None and row[k] < 0 for k in ("export_mass_t", "import_mirror_mass_t")):
            raise ValueError("Negative mass requires a documented rule")
    output_dir.mkdir(parents=True)

    scale_rows, granularity_rows, ranks, selections = [], [], [], []
    groups = {"all_six": rows, "spent_accumulator_label": [r for r in rows if r["product"] in SPENT]}
    for group, grouped in groups.items():
        for window, subset in (
            ("2022-2025", grouped), ("2022-2024", [r for r in grouped if r["year"] <= 2024]),
        ):
            for label, keys in (
                ("product_year_dyad", ("product", "year", "origin", "destination")),
                ("annual_dyad_all_group_codes", ("year", "origin", "destination")),
                ("pooled_product_dyad", ("product", "origin", "destination")),
                ("pooled_dyad", ("origin", "destination")),
                ("pooled_origin_country", ("origin",)),
                ("pooled_destination_country", ("destination",)),
            ):
                scale_rows.append({"classification_group": group, "window": window, "aggregation_scale": label, **support_overlap(subset, keys)})
            destination_shares = {rule: reported_shares(subset, rule, ("destination",)) for rule in RULES}
            for rule in RULES:
                order = sorted(EU27, key=lambda c: (-destination_shares[rule].get((c,), 0.0), c))
                cumulative = 0.0
                for rank, country in enumerate(order, 1):
                    share = destination_shares[rule].get((country,), 0.0)
                    cumulative += share
                    ranks.append({"classification_group": group, "window": window, "report_rule": rule, "country": country,
                                  "published_mass_share": share, "rank_of_published_mass": rank, "cumulative_share": cumulative})
            for k in range(1, 6):
                selections.extend({"classification_group": group, "window": window, **s} for s in priority_sets(destination_shares, k))

        # Fixed classification, annual versus pooled time support comparison.
        for year in (2022, 2023, 2024, 2025):
            annual = [r for r in grouped if r["year"] == year]
            granularity_rows.append({"classification_group": group, "time_window": str(year),
                                     **support_overlap(annual, ("origin", "destination"))})
        granularity_rows.append({"classification_group": group, "time_window": "2022-2025",
                                 **support_overlap(grouped, ("origin", "destination"))})

    write_csv(output_dir / "aggregation_scale_sensitivity.csv", scale_rows)
    write_csv(output_dir / "fixed_classification_annual_pooled_sensitivity.csv", granularity_rows)
    write_csv(output_dir / "destination_reported_mass_ranks.csv", ranks)
    write_csv(output_dir / "information_priority_cross_view_coverage.csv", selections)
    source = input_dir / "eu27_mirror_comparison.csv"
    audit = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
             "country_population": list(EU27), "rows": len(rows), "classification_groups": list(groups),
             "windows": ["2022-2025", "2022-2024"], "priority_budgets_k": [1, 2, 3, 4, 5],
             "selection_algorithm": "Exhaustive combinations; lexicographic tie break at 1e-14 tolerance; minimise no costs and assume no capacities.",
             "minimax_views": list(RULES[:2]), "available_max_is_independent_source": False,
             "missing_policy": "None retained. Zero share is a zero contribution to available published mass, not physical zero imputation.",
             "analysis_status": "Exploratory descriptive analysis; not preregistered.",
             "outputs": ["aggregation_scale_sensitivity.csv", "fixed_classification_annual_pooled_sensitivity.csv", "destination_reported_mass_ranks.csv", "information_priority_cross_view_coverage.csv"]}
    (output_dir / "analysis_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir, args.output_dir), indent=2))
