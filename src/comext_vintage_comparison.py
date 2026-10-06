"""Compare genuinely retrieved snapshots without treating a window change as a revision."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from src.comext_information_check_diagnostics import quantity
from src.comext_network_quality_analysis import read_csv, write_csv


def compare_records(old, new, fields=("quantity_t", "value_eur")):
    def index(rows):
        result = {}
        for row in rows:
            key = tuple(row[k] for k in ("product", "year", "flow", "origin", "destination"))
            if key in result:
                raise ValueError("Duplicate declaration key")
            result[key] = row
        return result
    a, b = index(old), index(new)
    comparisons = []
    for key in sorted(a.keys() | b.keys()):
        for field in fields:
            first = quantity(a[key][field]) if key in a else None
            second = quantity(b[key][field]) if key in b else None
            status = "unchanged" if first == second else "changed_numeric" if first is not None and second is not None else "availability_changed"
            comparisons.append(dict(zip(("product", "year", "flow", "origin", "destination"), key)) | {
                "field": field, "old_value": first, "new_value": second,
                "absolute_difference": abs(second - first) if first is not None and second is not None else None,
                "relative_difference_percent": 100 * abs(second - first) / abs(first) if first not in (None, 0) and second is not None else None,
                "comparison_status": status})
    return comparisons


def run(old_dir, new_dir, old_raw, new_raw, output_dir):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    filename = "eu27_directed_trade_observations.csv"
    old, new = read_csv(old_dir / filename), read_csv(new_dir / filename)
    comparisons = compare_records(old, new)
    summaries = []
    for window, subset in [("2022-2025", comparisons), ("2022-2024", [r for r in comparisons if int(r["year"]) <= 2024]), ("2025", [r for r in comparisons if r["year"] == "2025"])]:
        summaries.append({"window": window, "compared_measures": len(subset),
                          **{status: sum(r["comparison_status"] == status for r in subset) for status in ("unchanged", "changed_numeric", "availability_changed")},
                          "max_absolute_mass_change_t": max((r["absolute_difference"] for r in subset if r["field"] == "quantity_t" and r["absolute_difference"] is not None), default=None)})
    old_manifest, new_manifest = [json.loads((p / "manifest.json").read_text(encoding="utf-8")) for p in (old_raw, new_raw)]
    audit = {"old_retrieved_at_utc": old_manifest["retrieved_at_utc"], "new_retrieved_at_utc": new_manifest["retrieved_at_utc"],
             "old_dataset_update": old_manifest["retrieved_data_version"], "new_dataset_update": new_manifest["retrieved_data_version"],
             "old_observation_rows": len(old), "new_observation_rows": len(new),
             "old_derived_sha256": hashlib.sha256((old_dir / filename).read_bytes()).hexdigest(),
             "new_derived_sha256": hashlib.sha256((new_dir / filename).read_bytes()).hexdigest(),
             "windows": summaries,
             "claim_boundary": "Only these two actual retrievals and selected EU27 declarations are compared; no claim that 2025 is final or immune to later revision."}
    output_dir.mkdir(parents=True)
    write_csv(output_dir / "vintage_measure_comparison.csv", comparisons)
    write_csv(output_dir / "vintage_summary.csv", summaries)
    (output_dir / "audit_summary.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("old-dir", "new-dir", "old-raw", "new-raw", "output-dir"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    run(args.old_dir, args.new_dir, args.old_raw, args.new_raw, args.output_dir)
