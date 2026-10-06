from src.comext_network_quality_analysis import (
    edge_metrics,
    mirror_metrics,
    number,
    network_rule_sensitivity,
    route_overlap_by_threshold,
)
import pytest


def test_period_network_aggregates_repeated_route_mass_without_counting_years_as_edges():
    result = edge_metrics([
        {"origin": "DE", "destination": "FR", "quantity_t": 10.0, "value_eur": 100.0},
        {"origin": "DE", "destination": "FR", "quantity_t": 20.0, "value_eur": 200.0},
        {"origin": "FR", "destination": "DE", "quantity_t": 0.0, "value_eur": 5.0},
    ])
    assert result["positive_reported_routes"] == 1
    assert result["positive_reported_mass_t"] == 30.0
    assert result["top_route_mass_share"] == 1.0
    assert result["zero_mass_nonzero_value_records"] == 1


def test_mirror_asymmetry_is_symmetric_and_missing_sides_are_not_zero_filled():
    result = mirror_metrics([
        {"mirror_status": "both", "export_mass_t": 30.0, "import_mirror_mass_t": 10.0,
         "origin": "DE", "destination": "FR"},
        {"mirror_status": "export_only", "export_mass_t": 50.0, "import_mirror_mass_t": None,
         "origin": "NL", "destination": "BE"},
        {"mirror_status": "both", "export_mass_t": 0.0, "import_mirror_mass_t": 0.0,
         "origin": "IT", "destination": "AT"},
    ])
    # 200 * (30 - 10) / (30 + 10) = 100 percentage points.
    assert result["both_sides_share_of_union_pct"] == pytest.approx(200 / 3)
    assert result["matched_positive_or_nonzero_pair_count"] == 1
    assert result["median_abs_symmetric_asymmetry_pct"] == 100.0
    assert result["export_mass_in_matched_pairs_t"] == 30.0
    assert result["mirror_import_mass_in_matched_pairs_t"] == 10.0


def test_all_missing_or_zero_pairs_have_no_asymmetry_estimate():
    result = mirror_metrics([
        {"mirror_status": "both", "export_mass_t": 0.0, "import_mirror_mass_t": 0.0,
         "origin": "ES", "destination": "PT"},
        {"mirror_status": "both", "export_mass_t": None, "import_mirror_mass_t": None,
         "origin": "FR", "destination": "BE"},
    ])
    assert result["matched_positive_or_nonzero_pair_count"] == 0
    assert result["median_abs_symmetric_asymmetry_pct"] is None
    assert result["mass_weighted_abs_symmetric_asymmetry_pct"] is None


def test_numeric_parser_preserves_missing_and_accepts_parsed_floats():
    assert number(3.5) == 3.5
    assert number(0) == 0.0
    assert number("") is None
    assert number(None) is None


def test_route_overlap_threshold_excludes_small_and_missing_reports_without_imputation():
    rows = [
        {"product": "X", "year": 2023, "flow": "export", "origin": "DE", "destination": "FR", "quantity_t": 0.5},
        {"product": "X", "year": 2023, "flow": "import", "origin": "DE", "destination": "FR", "quantity_t": 2.0},
        {"product": "X", "year": 2023, "flow": "export", "origin": "IT", "destination": "ES", "quantity_t": None},
        {"product": "X", "year": 2023, "flow": "import", "origin": "NL", "destination": "BE", "quantity_t": 5.0},
    ]
    base, strict = route_overlap_by_threshold(rows, (0.0, 1.0))
    assert (base["export_positive_reported_routes"], base["import_mirror_positive_reported_routes"]) == (1, 2)
    assert base["positive_report_support_jaccard"] == pytest.approx(1 / 2)
    assert (strict["export_positive_reported_routes"], strict["import_mirror_positive_reported_routes"]) == (0, 2)
    assert strict["positive_report_support_jaccard"] == 0.0


def test_threshold_comparison_uses_strict_cutoff_and_rejects_negative_threshold():
    row = {"product": "X", "year": 2024, "flow": "export", "origin": "A", "destination": "B", "quantity_t": 1.0}
    result = route_overlap_by_threshold([row], (1.0,))[0]
    assert result["union_routes"] == 0
    assert result["positive_report_support_jaccard"] is None
    with pytest.raises(ValueError, match="non-negative"):
        route_overlap_by_threshold([row], (-0.1,))


def test_network_input_rules_do_not_zero_fill_missing_sides_and_condition_min_max():
    rows = [
        {"origin": "DE", "destination": "FR", "export_mass_t": 10.0, "import_mirror_mass_t": 12.0},
        {"origin": "IT", "destination": "ES", "export_mass_t": 5.0, "import_mirror_mass_t": None},
        {"origin": "NL", "destination": "BE", "export_mass_t": None, "import_mirror_mass_t": 0.0},
    ]
    results = {r["network_input_rule"]: r for r in network_rule_sensitivity(rows)}
    assert results["exporter_report_only"]["pooled_reported_mass_t_2022_2025"] == 15.0
    assert results["importer_mirror_report_only"]["pooled_reported_mass_t_2022_2025"] == 12.0
    assert results["available_report_max_union"]["pooled_reported_mass_t_2022_2025"] == 17.0
    assert results["available_report_max_union"]["eligible_product_year_dyad_report_rows"] == 3
    assert results["matched_report_max_only"]["pooled_reported_mass_t_2022_2025"] == 12.0
    assert results["matched_report_min_only"]["pooled_reported_mass_t_2022_2025"] == 10.0
    assert results["available_report_max_union"]["positive_pooled_directed_routes"] == 2
