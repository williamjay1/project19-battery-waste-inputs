"""Auditable diagnostics for the post-2022 EU battery-waste Comext snapshot.

This is a descriptive measurement analysis of reported goods-trade statistics.
It does not infer EV-specific waste, physical shipments, or treatment-facility
intake. Missing partner-year observations remain unobserved, never zero-filled.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def hhi(values: list[float]) -> float | None:
    total = sum(values)
    if total <= 0:
        return None
    return sum((x / total) ** 2 for x in values if x > 0)


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def edge_metrics(rows: list[dict]) -> dict:
    positive = [r for r in rows if r["quantity_t"] is not None and r["quantity_t"] > 0]
    mass = sum(r["quantity_t"] for r in positive)
    route_mass: dict[tuple[str, str], float] = defaultdict(float)
    origin_mass: dict[str, float] = defaultdict(float)
    for r in positive:
        key = (r["origin"], r["destination"])
        route_mass[key] += r["quantity_t"]
        origin_mass[r["origin"]] += r["quantity_t"]
    return {
        "positive_reported_routes": len(route_mass),
        "exporter_countries_with_positive_records": len(origin_mass),
        "destination_countries_with_positive_records": len({d for _, d in route_mass}),
        "positive_reported_mass_t": mass,
        "positive_route_hhi": hhi(list(route_mass.values())),
        "exporter_mass_hhi": hhi(list(origin_mass.values())),
        "top_route_mass_share": max(route_mass.values()) / mass if mass > 0 else None,
        "zero_mass_nonzero_value_records": sum(
            1 for r in rows if r["quantity_t"] == 0 and r["value_eur"] not in (None, 0)
        ),
        "negative_mass_records": sum(1 for r in rows if r["quantity_t"] is not None and r["quantity_t"] < 0),
    }


def mirror_metrics(rows: list[dict]) -> dict:
    # The input is one product/year slice of the union of directed pair reports.
    both = [
        r for r in rows
        if r["mirror_status"] == "both"
        and r["export_mass_t"] is not None
        and r["import_mirror_mass_t"] is not None
    ]
    pair_asymmetry: list[float] = []
    exp_sum = imp_sum = abs_diff_sum = 0.0
    compared_mass = 0
    for r in both:
        e = r["export_mass_t"]
        i = r["import_mirror_mass_t"]
        denom = e + i
        if denom > 0:
            signed = 200.0 * (e - i) / denom
            pair_asymmetry.append(abs(signed))
            exp_sum += e
            imp_sum += i
            abs_diff_sum += abs(e - i)
            compared_mass += 1
    matched_route_set = {(r["origin"], r["destination"]) for r in both}
    return {
        "pair_year_union_count": len(rows),
        "both_sides_with_mass": len(both),
        "export_only_count": sum(r["mirror_status"] == "export_only" for r in rows),
        "import_only_count": sum(r["mirror_status"] == "import_only" for r in rows),
        "both_sides_share_of_union_pct": 100 * len(both) / len(rows) if rows else None,
        "matched_positive_or_nonzero_pair_count": compared_mass,
        "median_abs_symmetric_asymmetry_pct": median(pair_asymmetry) if pair_asymmetry else None,
        "mass_weighted_abs_symmetric_asymmetry_pct": 200 * abs_diff_sum / (exp_sum + imp_sum) if exp_sum + imp_sum else None,
        "signed_aggregate_symmetric_asymmetry_pct": 200 * (exp_sum - imp_sum) / (exp_sum + imp_sum) if exp_sum + imp_sum else None,
        "export_mass_in_matched_pairs_t": exp_sum,
        "mirror_import_mass_in_matched_pairs_t": imp_sum,
        "matched_route_count": len(matched_route_set),
    }


def route_overlap_by_threshold(
    rows: list[dict], thresholds_t: tuple[float, ...] = (0.0, 0.1, 1.0, 10.0)
) -> list[dict]:
    """Compare positive reported route supports without treating non-reports as zero.

    A route enters a reporter-side set only when that side has an observed mass
    strictly greater than the declared threshold. The statistic is a comparison
    of reported positive supports, not a measure of true physical-network recall.
    """
    if any(t < 0 for t in thresholds_t):
        raise ValueError("route-mass thresholds must be non-negative")
    slices: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        slices[(str(row["product"]), int(row["year"]))].append(row)

    result: list[dict] = []
    for threshold in thresholds_t:
        for (product, year), slice_rows in sorted(slices.items()):
            exporter_routes = {
                (r["origin"], r["destination"])
                for r in slice_rows
                if r["flow"] == "export"
                and r["quantity_t"] is not None
                and r["quantity_t"] > threshold
            }
            importer_routes = {
                (r["origin"], r["destination"])
                for r in slice_rows
                if r["flow"] == "import"
                and r["quantity_t"] is not None
                and r["quantity_t"] > threshold
            }
            union = exporter_routes | importer_routes
            intersection = exporter_routes & importer_routes
            result.append({
                "product": product,
                "year": year,
                "reported_mass_threshold_t_strictly_greater_than": threshold,
                "export_positive_reported_routes": len(exporter_routes),
                "import_mirror_positive_reported_routes": len(importer_routes),
                "intersection_routes": len(intersection),
                "union_routes": len(union),
                "positive_report_support_jaccard": len(intersection) / len(union) if union else None,
                "interpretation": "Reported positive-route support only; unreported dyads are unknown, not zero or confirmed absent.",
            })
    return result


def network_rule_sensitivity(rows: list[dict]) -> list[dict]:
    """Quantify alternative reported-mass inputs for a pooled route network.

    The max rule follows the reported-pair reconciliation used in Martínez et
    al. (2022), but is applied only to available Comext reports. One-sided rows
    retain their observed side; missing values are never set to zero. Matched-
    only max/min variants deliberately condition on both reports being present.
    None of these rules identifies physical shipment mass.
    """
    route_mass_by_rule: dict[str, dict[tuple[str, str], float]] = {
        name: defaultdict(float) for name in (
            "exporter_report_only",
            "importer_mirror_report_only",
            "available_report_max_union",
            "matched_report_max_only",
            "matched_report_min_only",
        )
    }
    eligible_rows = {name: 0 for name in route_mass_by_rule}

    for row in rows:
        e = row["export_mass_t"]
        i = row["import_mirror_mass_t"]
        route = (row["origin"], row["destination"])
        if e is not None:
            eligible_rows["exporter_report_only"] += 1
            if e > 0:
                route_mass_by_rule["exporter_report_only"][route] += e
        if i is not None:
            eligible_rows["importer_mirror_report_only"] += 1
            if i > 0:
                route_mass_by_rule["importer_mirror_report_only"][route] += i
        if e is not None or i is not None:
            eligible_rows["available_report_max_union"] += 1
            available = [x for x in (e, i) if x is not None]
            selected = max(available)
            if selected > 0:
                route_mass_by_rule["available_report_max_union"][route] += selected
        if e is not None and i is not None:
            eligible_rows["matched_report_max_only"] += 1
            eligible_rows["matched_report_min_only"] += 1
            maximum, minimum = max(e, i), min(e, i)
            if maximum > 0:
                route_mass_by_rule["matched_report_max_only"][route] += maximum
            if minimum > 0:
                route_mass_by_rule["matched_report_min_only"][route] += minimum

    descriptions = {
        "exporter_report_only": "Exporter declarations only; missing importer mirrors remain unknown.",
        "importer_mirror_report_only": "Importer mirrors only; missing exporter declarations remain unknown.",
        "available_report_max_union": "Maximum of available side reports; one-sided rows retain the observed value, not zero-filled.",
        "matched_report_max_only": "Maximum only where both side reports are observed; conditional matched subset.",
        "matched_report_min_only": "Minimum only where both side reports are observed; conditional matched subset, not a physical lower bound.",
    }
    out = []
    for name, routes in route_mass_by_rule.items():
        total = sum(routes.values())
        top_route = max(routes, key=routes.get) if routes else None
        out.append({
            "network_input_rule": name,
            "rule_definition": descriptions[name],
            "eligible_product_year_dyad_report_rows": eligible_rows[name],
            "positive_pooled_directed_routes": len(routes),
            "pooled_reported_mass_t_2022_2025": total,
            "route_hhi": hhi(list(routes.values())),
            "top_route_mass_share": routes[top_route] / total if top_route and total > 0 else None,
            "top_route_origin": top_route[0] if top_route else None,
            "top_route_destination": top_route[1] if top_route else None,
            "interpretation": "Alternative summaries of public declarations; none estimates complete physical or EV-specific shipments.",
        })
    return out


def run(input_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    observations = read_csv(input_dir / "eu27_directed_trade_observations.csv")
    mirror_rows = read_csv(input_dir / "eu27_mirror_comparison.csv")
    member_rows = read_csv(input_dir / "eu27_member_aggregate_trade.csv")
    for r in observations:
        r["year"] = int(r["year"])
        r["quantity_t"] = number(r["quantity_t"])
        r["value_eur"] = number(r["value_eur"])
    for r in mirror_rows:
        r["year"] = int(r["year"])
        r["export_mass_t"] = number(r["export_mass_t"])
        r["import_mirror_mass_t"] = number(r["import_mirror_mass_t"])
    for r in member_rows:
        r["year"] = int(r["year"])
        r["quantity_t"] = number(r["quantity_t"])

    products = sorted({r["product"] for r in observations})
    years = sorted({r["year"] for r in observations})
    product_desc = {r["product"]: r["product_description"] for r in observations}
    annual: list[dict] = []
    mirror_annual: list[dict] = []
    route_sensitivity: list[dict] = []

    # Networks are separately reconstructed from exporter and importer reports.
    for product in products:
        for year in years:
            exp = [r for r in observations if r["product"] == product and r["year"] == year and r["flow"] == "export"]
            imp = [r for r in observations if r["product"] == product and r["year"] == year and r["flow"] == "import"]
            mirror_slice = [r for r in mirror_rows if r["product"] == product and r["year"] == year]
            exp_m = edge_metrics(exp)
            imp_m = edge_metrics(imp)
            positive_exp = {(r["origin"], r["destination"]) for r in exp if r["quantity_t"] is not None and r["quantity_t"] > 0}
            positive_imp = {(r["origin"], r["destination"]) for r in imp if r["quantity_t"] is not None and r["quantity_t"] > 0}
            union = positive_exp | positive_imp
            intersection = positive_exp & positive_imp
            annual.append({
                "product": product, "product_description": product_desc[product], "year": year,
                "export_declaration_rows": len(exp), "export_declaration_mass_t_all_rows": sum(r["quantity_t"] for r in exp if r["quantity_t"] is not None),
                "export_declaration_value_eur_all_rows": sum(r["value_eur"] for r in exp if r["value_eur"] is not None),
                **{f"export_{k}": v for k, v in exp_m.items()},
                "import_mirror_declaration_rows": len(imp), "import_mirror_mass_t_all_rows": sum(r["quantity_t"] for r in imp if r["quantity_t"] is not None),
                **{f"import_{k}": v for k, v in imp_m.items()},
                "possible_directed_eu27_pairs": 27 * 26,
                "export_positive_edge_density_pct_not_coverage": 100 * len(positive_exp) / (27 * 26),
                "positive_edge_jaccard_export_vs_import_reports": len(intersection) / len(union) if union else None,
                "positive_edge_union_count": len(union), "positive_edge_intersection_count": len(intersection),
            })
            mirror_annual.append({
                "product": product, "product_description": product_desc[product], "year": year,
                **mirror_metrics(mirror_slice),
            })
            route_sensitivity.append({
                "product": product, "year": year,
                "export_positive_routes": len(positive_exp), "import_mirror_positive_routes": len(positive_imp),
                "positive_route_intersection": len(intersection), "positive_route_union": len(union),
                "jaccard_positive_route_overlap": len(intersection) / len(union) if union else None,
                "export_route_hhi": exp_m["positive_route_hhi"], "import_mirror_route_hhi": imp_m["positive_route_hhi"],
                "export_top_route_share": exp_m["top_route_mass_share"], "import_mirror_top_route_share": imp_m["top_route_mass_share"],
            })

    period: list[dict] = []
    period_mirrors: list[dict] = []
    for product in products:
        exp = [r for r in observations if r["product"] == product and r["flow"] == "export"]
        imp = [r for r in observations if r["product"] == product and r["flow"] == "import"]
        mirror_slice = [r for r in mirror_rows if r["product"] == product]
        exp_metrics = edge_metrics(exp)
        imp_metrics = edge_metrics(imp)
        period.append({
            "product": product, "product_description": product_desc[product], "period": f"{min(years)}-{max(years)}",
            "export_declaration_rows": len(exp), "export_declaration_mass_t_all_rows": sum(r["quantity_t"] for r in exp if r["quantity_t"] is not None),
            "export_declaration_value_eur_all_rows": sum(r["value_eur"] for r in exp if r["value_eur"] is not None),
            **{f"export_{k}": v for k, v in exp_metrics.items()},
            "import_mirror_declaration_rows": len(imp), "import_mirror_mass_t_all_rows": sum(r["quantity_t"] for r in imp if r["quantity_t"] is not None),
            **{f"import_{k}": v for k, v in imp_metrics.items()},
        })
        period_mirrors.append({"product": product, "product_description": product_desc[product], **mirror_metrics(mirror_slice)})

    threshold_sensitivity = route_overlap_by_threshold(observations)
    threshold_summary = []
    for threshold in sorted({r["reported_mass_threshold_t_strictly_greater_than"] for r in threshold_sensitivity}):
        values = [
            r["positive_report_support_jaccard"] for r in threshold_sensitivity
            if r["reported_mass_threshold_t_strictly_greater_than"] == threshold
            and r["positive_report_support_jaccard"] is not None
        ]
        threshold_summary.append({
            "threshold_t": threshold,
            "nonempty_product_year_slices": len(values),
            "median_jaccard": median(values) if values else None,
            "minimum_jaccard": min(values) if values else None,
            "maximum_jaccard": max(values) if values else None,
        })
    network_rules = network_rule_sensitivity(mirror_rows)

    # Check whether bilateral detail sums to the officially supplied intra-EU
    # aggregate for the same reporter, direction, code and year.
    detailed: dict[tuple, float] = defaultdict(float)
    detailed_missing: dict[tuple, int] = defaultdict(int)
    detailed_rows: dict[tuple, int] = defaultdict(int)
    for r in observations:
        reporter = r["origin"] if r["flow"] == "export" else r["destination"]
        key = (r["product"], r["year"], r["flow"], reporter)
        detailed_rows[key] += 1
        if r["quantity_t"] is None:
            detailed_missing[key] += 1
        else:
            detailed[key] += r["quantity_t"]
    aggregate: list[dict] = []
    agg_lookup = {(r["product"], r["year"], r["flow"], r["country"]): r for r in member_rows if r["partner_aggregate"] == "intra_eu27"}
    for key, row in sorted(agg_lookup.items()):
        det = detailed.get(key)
        missing_detail_count = detailed_missing.get(key, 0)
        agg = row["quantity_t"]
        # Do not treat a missing partner quantity as zero in the reconciliation.
        row_count = detailed_rows.get(key, 0)
        det_complete = det if row_count > 0 and missing_detail_count == 0 else None
        diff = det_complete - agg if det_complete is not None and agg is not None else None
        status = (
            "no_published_partner_detail" if row_count == 0
            else "incomplete_detail_missing_mass" if missing_detail_count > 0
            else "complete_detail"
        )
        aggregate.append({
            "product": key[0], "year": key[1], "flow": key[2], "reporter": key[3],
            "intra_eu_aggregate_mass_t": agg, "sum_of_published_member_partner_mass_t": det_complete,
            "published_partner_detail_rows": row_count,
            "detail_rows_with_missing_mass": missing_detail_count,
            "reconciliation_status": status,
            "detail_minus_aggregate_t": diff,
            "abs_relative_difference_pct": 100 * abs(diff) / abs(agg) if diff is not None and agg not in (None, 0) else None,
            "interpretation": "Published aggregate-to-detail coherence check; not a completeness or actual-shipment validation.",
        })

    # Product state/sorting contrasts are descriptive, not a claim about chemistry.
    states = {
        "85491320": ("spent accumulators", "sorted by chemical type"),
        "85491390": ("waste and scrap", "sorted by chemical type"),
        "85491420": ("spent accumulators", "unsorted"),
        "85491490": ("waste and scrap", "unsorted"),
        "85491920": ("spent accumulators", "sorted but not by chemical type"),
        "85491990": ("waste and scrap", "sorted but not by chemical type"),
    }
    categories = []
    total_mass = sum(r["export_positive_reported_mass_t"] or 0 for r in period)
    for r in period:
        state, sorting = states[r["product"]]
        categories.append({
            "product": r["product"], "product_description": r["product_description"],
            "declared_product_state": state, "declared_sorting_class": sorting,
            "period_positive_export_mass_t": r["export_positive_reported_mass_t"],
            "share_of_six_code_positive_export_mass_pct": 100 * r["export_positive_reported_mass_t"] / total_mass if total_mass else None,
            "export_positive_routes_4y": r["export_positive_reported_routes"],
            "export_positive_route_hhi_4y": r["export_positive_route_hhi"],
            "limit": "Customs product label only; not EV-specific, Li-ion-specific, or destination/treatment evidence.",
        })

    aggregation_specs = [
        ("all_six_selected_classes", set(products), "Six selected non-lead/cadmium/mercury CN8 classes"),
        ("spent_accumulator_label", {"85491320", "85491420", "85491920"}, "Codes whose product label says spent electric accumulators"),
        ("mixed_waste_scrap_label", {"85491390", "85491490", "85491990"}, "Codes covering waste/scrap of primary cells, batteries and accumulators"),
        ("sorted_by_chemical_type", {"85491320", "85491390"}, "Codes labelled sorted by chemical type"),
        ("unsorted", {"85491420", "85491490"}, "Codes labelled unsorted"),
        ("sorted_not_by_chemical_type", {"85491920", "85491990"}, "Codes labelled sorted but not by chemical type"),
    ]
    aggregation_sensitivity: list[dict] = []
    for group_name, group_codes, group_description in aggregation_specs:
        group_obs = [r for r in observations if r["product"] in group_codes]
        group_export = [r for r in group_obs if r["flow"] == "export"]
        group_import = [r for r in group_obs if r["flow"] == "import"]
        export_metrics = edge_metrics(group_export)
        import_metrics = edge_metrics(group_import)
        export_routes = {(r["origin"], r["destination"]) for r in group_export if r["quantity_t"] is not None and r["quantity_t"] > 0}
        import_routes = {(r["origin"], r["destination"]) for r in group_import if r["quantity_t"] is not None and r["quantity_t"] > 0}
        route_union = export_routes | import_routes
        aggregation_sensitivity.append({
            "aggregation": group_name, "description": group_description,
            "included_cn8_codes": ";".join(sorted(group_codes)),
            "period": f"{min(years)}-{max(years)}",
            "export_positive_mass_t": export_metrics["positive_reported_mass_t"],
            "export_positive_routes": export_metrics["positive_reported_routes"],
            "export_positive_route_hhi": export_metrics["positive_route_hhi"],
            "export_top_route_share": export_metrics["top_route_mass_share"],
            "import_mirror_positive_mass_t": import_metrics["positive_reported_mass_t"],
            "import_mirror_positive_routes": import_metrics["positive_reported_routes"],
            "import_mirror_positive_route_hhi": import_metrics["positive_route_hhi"],
            "import_mirror_top_route_share": import_metrics["top_route_mass_share"],
            "positive_route_jaccard_export_vs_import_mirror": len(export_routes & import_routes) / len(route_union) if route_union else None,
            "interpretation_limit": "Aggregation sensitivity in reported customs classes; not observed EV routing or physical shipments.",
        })

    write_csv(output_dir / "annual_export_import_network_diagnostics.csv", annual)
    write_csv(output_dir / "annual_mirror_diagnostics.csv", mirror_annual)
    write_csv(output_dir / "period_export_import_network_diagnostics.csv", period)
    write_csv(output_dir / "period_mirror_diagnostics.csv", period_mirrors)
    write_csv(output_dir / "reporting_aggregate_coherence.csv", aggregate)
    write_csv(output_dir / "route_definition_sensitivity.csv", route_sensitivity)
    write_csv(output_dir / "cn8_category_composition.csv", categories)
    write_csv(output_dir / "classification_aggregation_sensitivity.csv", aggregation_sensitivity)
    write_csv(output_dir / "route_overlap_threshold_sensitivity.csv", threshold_sensitivity)
    write_csv(output_dir / "network_input_rule_sensitivity.csv", network_rules)

    matched_pairs = [
        r for r in mirror_rows
        if r["mirror_status"] == "both"
        and number(r["export_mass_t"]) is not None
        and number(r["import_mirror_mass_t"]) is not None
        and number(r["export_mass_t"]) + number(r["import_mirror_mass_t"]) > 0
    ]
    pooled_export_mass = sum(number(r["export_mass_t"]) for r in matched_pairs)
    pooled_import_mass = sum(number(r["import_mirror_mass_t"]) for r in matched_pairs)
    pooled_abs_difference = sum(abs(number(r["export_mass_t"]) - number(r["import_mirror_mass_t"])) for r in matched_pairs)
    export_mass_all = sum(r["quantity_t"] for r in observations if r["flow"] == "export" and r["quantity_t"] is not None)
    import_mass_all = sum(r["quantity_t"] for r in observations if r["flow"] == "import" and r["quantity_t"] is not None)
    accumulator_codes = {"85491320", "85491420", "85491920"}
    accumulator_mass = sum(r["export_positive_reported_mass_t"] or 0 for r in period if r["product"] in accumulator_codes)
    all_six_positive_mass = sum(r["export_positive_reported_mass_t"] or 0 for r in period)
    jaccards = [r["jaccard_positive_route_overlap"] for r in route_sensitivity if r["jaccard_positive_route_overlap"] is not None]
    aggregate_comparable = [r for r in aggregate if r["abs_relative_difference_pct"] is not None]
    summary = {
        "input_dir": str(input_dir),
        "period": [min(years), max(years)],
        "product_code_count": len(products),
        "eu27_directed_trade_observation_rows": len(observations),
        "unique_product_year_directed_pair_union_rows": len(mirror_rows),
        "mirror_pairs_reported_on_both_sides": sum(r["mirror_status"] == "both" for r in mirror_rows),
        "mirror_pair_both_sides_percentage": 100 * sum(r["mirror_status"] == "both" for r in mirror_rows) / len(mirror_rows) if mirror_rows else None,
        "export_positive_mass_total_t": export_mass_all,
        "import_mirror_mass_total_t": import_mass_all,
        "export_positive_value_sum_eur": sum(r["export_declaration_value_eur_all_rows"] for r in period),
        "explicit_spent_electric_accumulator_label_mass_t": accumulator_mass,
        "explicit_spent_electric_accumulator_label_share_pct_of_six_code_mass": 100 * accumulator_mass / all_six_positive_mass if all_six_positive_mass else None,
        "matched_pair_positive_mass_records": len(matched_pairs),
        "matched_export_mass_t": pooled_export_mass,
        "matched_import_mirror_mass_t": pooled_import_mass,
        "matched_pair_mass_weighted_abs_symmetric_asymmetry_pct": 200 * pooled_abs_difference / (pooled_export_mass + pooled_import_mass) if pooled_export_mass + pooled_import_mass else None,
        "matched_pairs_share_of_export_mass_pct": 100 * pooled_export_mass / export_mass_all if export_mass_all else None,
        "matched_pairs_share_of_import_mirror_mass_pct": 100 * pooled_import_mass / import_mass_all if import_mass_all else None,
        "annual_positive_route_jaccard_median": median(jaccards) if jaccards else None,
        "annual_positive_route_jaccard_min": min(jaccards) if jaccards else None,
        "annual_positive_route_jaccard_max": max(jaccards) if jaccards else None,
        "aggregate_coherence_rows": len(aggregate),
        "aggregate_rows_comparable_to_detail": len(aggregate_comparable),
        "aggregate_comparable_within_1pct": sum(r["abs_relative_difference_pct"] <= 1 for r in aggregate_comparable),
        "classification_aggregation_sensitivity_rows": len(aggregation_sensitivity),
        "route_overlap_threshold_sensitivity": threshold_summary,
        "network_input_rule_sensitivity_rows": len(network_rules),
        "data_boundary": "Reported EU-27 intracommunity goods-trade statistics in selected CN8 classes; not EV-only waste, physical shipment permits, facility receipts, or complete movement coverage.",
    }
    (output_dir / "analysis_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
