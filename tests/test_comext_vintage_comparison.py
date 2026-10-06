from src.comext_vintage_comparison import compare_records


def row(q, value=1):
    return dict(product="85491320", year="2025", flow="export", origin="DE", destination="FR", quantity_t=q, value_eur=value)


def test_changed_zero_and_unknown_are_distinct():
    out = compare_records([row(0)], [row(10)])
    assert out[0]["comparison_status"] == "changed_numeric"
    assert out[0]["absolute_difference"] == 10
    assert out[0]["relative_difference_percent"] is None
    out = compare_records([row("")], [row(0)])
    assert out[0]["comparison_status"] == "availability_changed"


def test_missing_record_is_not_zero():
    out = compare_records([row(0)], [])
    assert all(r["comparison_status"] == "availability_changed" for r in out)
    assert all(r["new_value"] is None for r in out)


def test_identical_retrieval_has_no_changes():
    assert all(r["comparison_status"] == "unchanged" for r in compare_records([row(1)], [row(1)]))
