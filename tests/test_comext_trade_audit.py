from src.comext_trade_audit import EU27, finite_float, network_metrics


def test_blank_missing_and_invalid_observations_are_not_silently_zeroed():
    assert finite_float("") is None
    assert finite_float("   ") is None
    assert finite_float(None) is None
    assert finite_float("NaN") is None
    assert finite_float("confidential") is None
    assert finite_float("0") == 0.0


def test_network_summary_uses_only_reported_positive_mass_and_retains_missingness():
    result = network_metrics([
        {"origin": "DE", "destination": "FR", "quantity_t": 10.0, "value_eur": 100.0},
        {"origin": "DE", "destination": "NL", "quantity_t": None, "value_eur": 50.0},
        {"origin": "FR", "destination": "DE", "quantity_t": 0.0, "value_eur": 0.0},
    ])
    assert result["reported_positive_routes"] == 1
    assert result["declared_mass_t"] == 10.0
    assert result["declared_trade_value_eur"] == 150.0
    assert result["reported_route_fraction_not_coverage"] == round(1 / (27 * 26), 6)


def test_eu27_scope_includes_all_27_members_including_malta():
    assert len(EU27) == 27
    assert "MT" in EU27
    assert "GB" not in EU27
