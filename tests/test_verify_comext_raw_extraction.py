from decimal import Decimal

import pytest

from src.verify_comext_raw_extraction import numeric, verify_rows


def fixture():
    key = ("85491320", "2023", "import", "DE", "FR")
    source = {(*key, "QUANTITY_IN_100KG"): (Decimal("12"), "FR", "DE"),
              (*key, "VALUE_IN_EUROS"): (Decimal("99"), "FR", "DE")}
    row = dict(zip(("product", "year", "flow", "origin", "destination"), key))
    row.update(reporter="FR", partner="DE", quantity_t="1.2", value_eur="99",
               quantity_observation_present="True", value_observation_present="True")
    return source, row


def test_full_import_orientation_and_conversion():
    source, row = fixture()
    result = verify_rows(source, [row])
    assert result["independently_recomputed_import_mass_t"] == 1.2
    assert result["verified_source_measure_rows"] == 2


def test_wrong_orientation_wrong_unit_and_omission_fail():
    source, row = fixture()
    with pytest.raises(ValueError, match="orientation"):
        verify_rows(source, [{**row, "reporter": "DE", "partner": "FR"}])
    with pytest.raises(ValueError, match="Unit/value"):
        verify_rows(source, [{**row, "quantity_t": "12"}])
    with pytest.raises(ValueError, match="omits"):
        verify_rows(source, [])


def test_missing_and_invalid_values_are_detected_not_zeroed():
    assert all(numeric(v) is None for v in (None, "", " ", "NaN", "Infinity", "confidential"))
    assert numeric("0") == Decimal(0)
    source, row = fixture()
    with pytest.raises(ValueError, match="Missing-value"):
        verify_rows(source, [{**row, "quantity_t": ""}])
