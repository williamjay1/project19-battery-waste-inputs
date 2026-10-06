import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from battery_scope_identification import eligibility, bounds, number, ranking
from scope_decision_certificate import margin

def row(code="200133", description="", operation="R4", tonnes=10):
    return {"low_code": code, "description": description, "r_code": operation, "d_code": "", "quantity_t": tonnes}

@pytest.mark.parametrize("value", [None, "", " ", "nan", "inf", "-1", "abc"])
def test_missing_or_bad_quantity_fails(value):
    with pytest.raises(ValueError):
        number(value)

def test_reported_zero_is_not_missing():
    assert number("0") == 0

def test_a1170_nickel_cadmium_does_not_become_lithium():
    assert eligibility(row(code="160602"), "lithium_family", "all")[:2] == (0, 0)

def test_lithium_description_does_not_become_ev_or_lithium_ion():
    x = row(description="Lithium batteries")
    assert eligibility(x, "lithium_family", "all")[:2] == (1, 1)
    assert eligibility(x, "EV", "all")[:2] == (0, 1)

@pytest.mark.parametrize("operation", ["R12", "R13", "D10"])
def test_pretreatment_and_storage_are_not_r4(operation):
    assert eligibility(row(description="Lithium batteries", operation=operation), "lithium_family", "R4")[:2] == (0, 0)

def test_unknown_share_preserves_interval_and_can_reverse_rank():
    a = bounds([row(tonnes=100)], "EV", "R4")
    b = bounds([row(tonnes=10)], "EV", "R4")
    assert a == {"lower_t": 0, "upper_t": 100, "width_t": 100}
    assert ranking(a, b) == "not_identified"

def test_positive_explicit_lower_can_identify_report_label_rank():
    a = bounds([row(description="Lithium batteries", tonnes=100), row(tonnes=20)], "lithium_family", "R4")
    b = bounds([row(tonnes=10)], "lithium_family", "R4")
    assert ranking(a, b) == "NL_strictly_above_BE_in_report_conditioned_set"

def test_empty_target_is_not_measured_recovered_output():
    assert bounds([row(code="160602")], "lithium_family", "R4") == {"lower_t": 0, "upper_t": 0, "width_t": 0}

@pytest.mark.parametrize('target,stage', [('unknown','all'),('EV','unknown')])
def test_invalid_task_rejected_even_for_excluded_row(target,stage):
    with pytest.raises(ValueError):eligibility(row(code='160602'),target,stage)

def test_hazard_code_is_not_a_lithium_description():
    r=row();r['hazard_code']='H4.2'
    assert eligibility(r,'lithium_family','R4')[:2]==(0,1)

def test_adversarial_margin_not_a_confidence_interval():
    assert margin(100,10)==90
    assert margin(100,10,.5,.1)==pytest.approx(34)
    assert margin(100,10,1)<0
    with pytest.raises(ValueError):margin(100,10,relative_quantity_error=1)
