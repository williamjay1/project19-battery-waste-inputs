import pytest
from src.comext_information_check_diagnostics import diagnostics, quantity


@pytest.mark.parametrize("value", [None, "", "  "])
def test_unknown_is_not_zero(value):
    assert quantity(value) is None


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "invalid"])
def test_invalid_quantities_rejected(value):
    with pytest.raises(ValueError):
        quantity(value)


def test_pairing_denominators_and_missing_flags():
    rows = [dict(destination="DE", export_mass_t=10, import_mirror_mass_t=5),
            dict(destination="DE", export_mass_t=20, import_mirror_mass_t=""),
            dict(destination="FR", export_mass_t=0, import_mirror_mass_t=0),
            dict(destination="FR", export_mass_t=0, import_mirror_mass_t=5)]
    out = diagnostics(rows, {"DE", "FR"})
    assert out["matched_quantity_keys"] == 3
    assert out["matched_positive_sum_keys"] == 2
    assert out["matched_zero_sum_keys"] == 1
    assert out["unmatched_quantity_keys"] == 1
    assert out["mean_record_asymmetry_percent"] == pytest.approx(400 / 3)
    assert out["weighted_asymmetry_percent"] == 100
    assert out["matched_exporter_mass_share"] == pytest.approx(1 / 3)
    assert out["matched_importer_mass_share"] == 1


def test_empty_population_is_explicitly_undefined():
    out = diagnostics([], {"MT"})
    assert out["mean_record_asymmetry_percent"] is None
    assert out["weighted_asymmetry_percent"] is None
    assert out["matched_exporter_mass_share"] is None
    assert out["asymmetry_quality_flag"].startswith("undefined")


def test_country_average_is_distinct_from_record_average():
    rows = [dict(destination="DE", export_mass_t=10, import_mirror_mass_t=10),
            dict(destination="DE", export_mass_t=10, import_mirror_mass_t=10),
            dict(destination="FR", export_mass_t=0, import_mirror_mass_t=10)]
    out = diagnostics(rows, {"DE", "FR"})
    assert out["mean_record_asymmetry_percent"] == pytest.approx(200 / 3)
    assert out["equal_country_mean_asymmetry_percent"] == 100
