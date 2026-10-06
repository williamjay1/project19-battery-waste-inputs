import pytest

from src.comext_decision_input_analysis import priority_sets, report_value, reported_shares, share_overlap


def test_max_retains_available_report_and_normalisation_is_reported_accounting():
    rows = [
        {"destination": "DE", "export_mass_t": 5.0, "import_mirror_mass_t": None},
        {"destination": "FR", "export_mass_t": None, "import_mirror_mass_t": 10.0},
    ]
    assert report_value(rows[0], "importer_mirror") is None
    assert report_value(rows[0], "available_max") == 5.0
    assert reported_shares(rows, "available_max", ("destination",)) == {("DE",): 1 / 3, ("FR",): 2 / 3}
    assert share_overlap(reported_shares(rows, "exporter", ("destination",)), reported_shares(rows, "importer_mirror", ("destination",))) == 0.0


def test_minimax_exhaustive_selection_differs_from_one_reporter_optimum():
    shares = {
        "exporter": {("DE",): 0.7, ("FR",): 0.3},
        "importer_mirror": {("DE",): 0.1, ("FR",): 0.9},
        "available_max": {("DE",): 0.5, ("FR",): 0.5},
    }
    results = {r["selection_rule"]: r for r in priority_sets(shares, 1)}
    assert results["exporter"]["selected_destination_countries"] == "DE"
    assert results["minimax_two_reporter_views"]["selected_destination_countries"] == "FR"
    assert results["minimax_two_reporter_views"]["worst_share_under_two_reporter_views"] == pytest.approx(0.3)
    with pytest.raises(ValueError):
        priority_sets(shares, 0)
