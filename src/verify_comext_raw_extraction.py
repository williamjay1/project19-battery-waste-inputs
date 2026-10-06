"""Independent source-to-table verification; imports no production extractor."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

COUNTRIES = frozenset("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
PRODUCTS = frozenset("85491320 85491390 85491420 85491490 85491920 85491990".split())


def numeric(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def source_records(raw_root: Path, entries: list[dict]) -> tuple[dict, dict]:
    records, source_countries = {}, set()
    missing, duplicates, negatives, verified = 0, 0, 0, 0
    for entry in entries:
        path = raw_root / entry["file"]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError(f"Raw digest mismatch: {path.name}")
        if len(payload) != entry["bytes"]:
            raise ValueError(f"Raw byte-count mismatch: {path.name}")
        verified += 1
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                source_countries.add(row["reporter"])
                if row["reporter"] not in COUNTRIES or row["partner"] not in COUNTRIES:
                    continue
                if row["product"] not in PRODUCTS or not 2022 <= int(row["TIME_PERIOD"]) <= 2025:
                    continue
                if row["freq"] != "A" or row["flow"] not in {"1", "2"}:
                    raise ValueError("Unexpected frequency or direction")
                direction = "export" if row["flow"] == "2" else "import"
                origin, destination = ((row["reporter"], row["partner"]) if direction == "export"
                                       else (row["partner"], row["reporter"]))
                key = (row["product"], row["TIME_PERIOD"], direction, origin, destination, row["indicators"])
                value = numeric(row["OBS_VALUE"])
                missing += value is None
                negatives += value is not None and value < 0
                if key in records:
                    duplicates += 1
                    raise ValueError(f"Duplicate source key: {key}")
                records[key] = (value, row["reporter"], row["partner"])
    if "EL" in source_countries:
        raise ValueError("Greece alias EL requires an explicit geographic concordance, not silent filtering")
    return records, {"hash_verified_raw_files": verified, "selected_raw_indicator_rows": len(records),
                     "source_missing_or_invalid_selected_values": missing, "source_duplicate_selected_keys": duplicates,
                     "source_negative_selected_values": negatives, "source_reporter_codes": sorted(source_countries),
                     "greece_code_GR_present": "GR" in source_countries}


def verify_rows(source: dict, derived: list[dict]) -> dict:
    checked, seen, zero_positive_value, totals = set(), set(), 0, {"export": Decimal(0), "import": Decimal(0)}
    for row in derived:
        key = (row["product"], row["year"], row["flow"], row["origin"], row["destination"])
        if key in seen:
            raise ValueError(f"Duplicate derived key: {key}")
        seen.add(key)
        for indicator, field, flag, scale in (
            ("QUANTITY_IN_100KG", "quantity_t", "quantity_observation_present", Decimal("0.1")),
            ("VALUE_IN_EUROS", "value_eur", "value_observation_present", Decimal(1)),
        ):
            source_key = (*key, indicator)
            expected, reporter, partner = source[source_key] if source_key in source else (None, None, None)
            actual = numeric(row[field])
            if source_key in source:
                checked.add(source_key)
                if (reporter, partner) != (row["reporter"], row["partner"]):
                    raise ValueError(f"Reporter/partner orientation mismatch: {key}")
            if (actual is None) != (expected is None):
                raise ValueError(f"Missing-value mismatch: {key} {indicator}")
            if actual is not None and abs(actual - expected * scale) > Decimal("0.00000001"):
                raise ValueError(f"Unit/value mismatch: {key} {indicator}")
            if row[flag] != str(expected is not None):
                raise ValueError(f"Availability flag mismatch: {key} {indicator}")
        quantity, value = numeric(row["quantity_t"]), numeric(row["value_eur"])
        if quantity is not None:
            totals[row["flow"]] += quantity
        zero_positive_value += quantity == 0 and value is not None and value > 0
    if checked != set(source):
        raise ValueError("The derived table omits selected source observations")
    return {"verified_derived_reporter_rows": len(seen), "verified_source_measure_rows": len(checked),
            "zero_quantity_positive_value_rows": zero_positive_value,
            "independently_recomputed_export_mass_t": float(totals["export"]),
            "independently_recomputed_import_mass_t": float(totals["import"]),
            "orientation_units_values_availability_and_source_coverage": "PASS"}


def run(raw_root: Path, derived: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((raw_root / "manifest.json").read_text(encoding="utf-8-sig"))
    source, audit = source_records(raw_root, manifest["raw_files"])
    with derived.open(encoding="utf-8-sig", newline="") as handle:
        audit.update(verify_rows(source, list(csv.DictReader(handle))))
    audit.update({"independence": "No production extraction or analysis functions imported; Decimal comparison of all selected source measures.",
                  "physical_flow_validation": False, "raw_manifest": str(raw_root / "manifest.json"),
                  "derived_table": str(derived), "derived_sha256": hashlib.sha256(derived.read_bytes()).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--derived", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.raw_root, args.derived, args.output), indent=2))
