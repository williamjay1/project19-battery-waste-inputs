"""Reproducible audit of EU-27 reported trade in battery-waste CN8 classes.

The script retrieves only filtered annual slices from Eurostat Comext DS-045409.
Raw API responses are written once to an immutable F: archive directory; all
derived tables are written to D:. Missing cells are never converted to zero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
EU27 = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
    "RO", "SK", "SI", "ES", "SE",
}
PRODUCTS = {
    "85491320": "Spent electric accumulators, sorted by chemical type, not containing lead, cadmium or mercury",
    "85491390": "Waste and scrap of primary cells, primary batteries and electric accumulators, sorted by chemical type, not containing lead, cadmium or mercury",
    "85491420": "Spent electric accumulators, unsorted, not containing lead, cadmium or mercury",
    "85491490": "Waste and scrap of primary cells, primary batteries and electric accumulators, unsorted, not containing lead, cadmium or mercury",
    "85491920": "Spent electric accumulators, sorted but not by chemical type, not containing lead, cadmium or mercury",
    "85491990": "Waste and scrap of primary cells, primary batteries and electric accumulators, sorted but not by chemical type, not containing lead, cadmium or mercury",
}
PRODUCT_META = {
    "85491320": {"product_state": "spent accumulators", "sorting_class": "sorted by chemical type"},
    "85491390": {"product_state": "waste and scrap", "sorting_class": "sorted by chemical type"},
    "85491420": {"product_state": "spent accumulators", "sorting_class": "unsorted"},
    "85491490": {"product_state": "waste and scrap", "sorting_class": "unsorted"},
    "85491920": {"product_state": "spent accumulators", "sorting_class": "sorted but not by chemical type"},
    "85491990": {"product_state": "waste and scrap", "sorting_class": "sorted but not by chemical type"},
}
INDICATORS = ("QUANTITY_IN_100KG", "VALUE_IN_EUROS")
FLOWS = ("1", "2")  # Eurostat trade convention: 1=imports, 2=exports.
YEARS = (2022, 2023, 2024, 2025)
RAW_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409/A...{product}.{flow}.{indicator}?format=SDMX-CSV&startPeriod=2022&endPeriod=2025"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, records: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Project19-open-data-research/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=90) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Eurostat request failed after 3 attempts: {url}: {last_error}")


def parse_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(text.splitlines()))


def finite_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def network_metrics(edges: list[dict]) -> dict:
    positive = [r for r in edges if r["quantity_t"] is not None and r["quantity_t"] > 0]
    total = sum(r["quantity_t"] for r in positive)
    shares = [r["quantity_t"] / total for r in positive] if total else []
    by_origin: dict[str, float] = defaultdict(float)
    for r in positive:
        by_origin[r["origin"]] += r["quantity_t"]
    origin_shares = [x / total for x in by_origin.values()] if total else []
    route_pairs = {(r["origin"], r["destination"]) for r in positive}
    return {
        "reported_positive_routes": len(positive),
        "origin_countries_with_positive_records": len(by_origin),
        "destination_countries_with_positive_records": len({r["destination"] for r in positive}),
        "declared_mass_t": round(total, 6),
        "declared_trade_value_eur": round(sum(r["value_eur"] for r in edges if r["value_eur"] is not None), 2),
        "top_route_mass_share": round(max(shares), 6) if shares else None,
        "route_hhi": round(sum(s * s for s in shares), 6) if shares else None,
        "origin_hhi": round(sum(s * s for s in origin_shares), 6) if origin_shares else None,
        "potential_directed_pairs_27x26": 27 * 26,
        "reported_route_fraction_not_coverage": round(len(route_pairs) / (27 * 26), 6),
    }


def run(raw_root: Path, derived_root: Path, reuse_raw: bool = False) -> None:
    if raw_root.exists() and not reuse_raw:
        raise FileExistsError(f"Raw snapshot path already exists; refusing to overwrite: {raw_root}")
    if not raw_root.exists() and reuse_raw:
        raise FileNotFoundError(f"Cannot reuse missing raw snapshot: {raw_root}")
    if derived_root.exists():
        raise FileExistsError(f"Derived output path already exists; refusing to overwrite: {derived_root}")
    if not reuse_raw:
        raw_root.mkdir(parents=True)
    derived_root.mkdir(parents=True)

    if reuse_raw:
        existing_manifest = json.loads((raw_root / "manifest.json").read_text(encoding="utf-8"))
        retrieved_at = existing_manifest["retrieved_at_utc"]
        raw_manifest: list[dict] = existing_manifest["raw_files"]
        manifest_by_file = {item["file"]: item for item in raw_manifest}
    else:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        raw_manifest = []
        manifest_by_file = {}
    raw_records: list[dict] = []
    member_aggregate: dict[tuple, dict] = {}

    write_csv(derived_root / "cn8_codebook.csv", [
        {
            "product": code,
            "eurostat_product_label": label,
            "product_state_group": PRODUCT_META[code]["product_state"],
            "declared_sorting_class": PRODUCT_META[code]["sorting_class"],
            "code_label_query": "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409?format=JSON&lang=en&freq=A&reporter=FR&partner=DE&product=" + code + "&flow=2&indicators=VALUE_IN_EUROS&time=2023",
            "interpretation_limit": "CN8 code excludes lead/cadmium/mercury but does not identify EV use or Li-ion chemistry.",
        }
        for code, label in PRODUCTS.items()
    ], ["product", "eurostat_product_label", "product_state_group", "declared_sorting_class", "code_label_query", "interpretation_limit"])

    for product in PRODUCTS:
        for flow in FLOWS:
            for indicator in INDICATORS:
                url = RAW_URL.format(product=product, flow=flow, indicator=indicator)
                filename = f"DS-045409_A_{product}_{flow}_{indicator}_2022-2025.csv"
                raw_path = raw_root / filename
                if reuse_raw:
                    payload = raw_path.read_bytes()
                    expected = manifest_by_file[filename]["sha256"]
                    if sha256(payload) != expected:
                        raise RuntimeError(f"Raw snapshot hash mismatch: {raw_path}")
                else:
                    payload = fetch(url)
                    raw_path.write_bytes(payload)
                    raw_path.chmod(0o444)
                    manifest_by_file[filename] = {
                        "file": filename,
                        "url": url,
                        "sha256": sha256(payload),
                        "bytes": len(payload),
                        "retrieved_at_utc": retrieved_at,
                        "indicator": indicator,
                        "flow": flow,
                        "product": product,
                        "time_window": "2022-2025",
                    }
                rows = parse_csv(payload)
                if not reuse_raw:
                    manifest_by_file[filename]["response_rows"] = len(rows)
                    manifest_by_file[filename]["dataset_last_update"] = rows[0].get("LAST UPDATE") if rows else None
                for row in rows:
                    if row.get("reporter") not in EU27:
                        continue
                    year = int(row["TIME_PERIOD"])
                    if year not in YEARS:
                        continue
                    reporter, partner = row["reporter"], row["partner"]
                    if partner in {"INT_EU27_2020", "EXT_EU27_2020"}:
                        key = (product, year, flow, reporter, partner)
                        target = member_aggregate.setdefault(key, {
                            "product": product,
                            "product_description": PRODUCTS[product],
                            "year": year,
                            "flow": "export" if flow == "2" else "import",
                            "country": reporter,
                            "partner_aggregate": "intra_eu27" if partner == "INT_EU27_2020" else "extra_eu27",
                            "quantity_t": None,
                            "value_eur": None,
                            "quantity_observation_present": False,
                            "value_observation_present": False,
                        })
                        obs_value = finite_float(row.get("OBS_VALUE"))
                        if indicator == "QUANTITY_IN_100KG":
                            target["quantity_t"] = obs_value * 0.1 if obs_value is not None else None
                            target["quantity_observation_present"] = obs_value is not None
                        else:
                            target["value_eur"] = obs_value
                            target["value_observation_present"] = obs_value is not None
                        continue
                    if partner not in EU27:
                        continue
                    # Orient all records as origin -> destination, irrespective of reporter flow.
                    origin, destination = (reporter, partner) if flow == "2" else (partner, reporter)
                    raw_records.append({
                        "product": product,
                        "product_description": PRODUCTS[product],
                        "year": year,
                        "flow": "export" if flow == "2" else "import",
                        "reporter": reporter,
                        "partner": partner,
                        "origin": origin,
                        "destination": destination,
                        "indicator": indicator,
                        "obs_value": finite_float(row.get("OBS_VALUE")),
                        "obs_status": row.get("OBS_STATUS"),
                    })
                if not reuse_raw:
                    time.sleep(0.25)

    raw_manifest = [manifest_by_file[f"DS-045409_A_{product}_{flow}_{indicator}_2022-2025.csv"]
                    for product in PRODUCTS for flow in FLOWS for indicator in INDICATORS]

    # Combine the two measures while retaining absent/non-numeric observations as missing.
    keyed: dict[tuple, dict] = {}
    for row in raw_records:
        key = (row["product"], row["year"], row["flow"], row["origin"], row["destination"])
        target = keyed.setdefault(key, {
            "product": row["product"],
            "product_description": row["product_description"],
            "year": row["year"],
            "flow": row["flow"],
            "origin": row["origin"],
            "destination": row["destination"],
            "reporter": row["reporter"],
            "partner": row["partner"],
            "quantity_t": None,
            "value_eur": None,
            "quantity_observation_present": False,
            "value_observation_present": False,
            "reported_status_flag": "",
        })
        if row["indicator"] == "QUANTITY_IN_100KG":
            target["quantity_t"] = row["obs_value"] * 0.1 if row["obs_value"] is not None else None
            target["quantity_observation_present"] = row["obs_value"] is not None
        else:
            target["value_eur"] = row["obs_value"]
            target["value_observation_present"] = row["obs_value"] is not None
        if row["obs_status"]:
            target["reported_status_flag"] = row["obs_status"]

    observations = sorted(keyed.values(), key=lambda r: (r["product"], r["year"], r["flow"], r["origin"], r["destination"]))
    write_csv(derived_root / "eu27_directed_trade_observations.csv", observations, [
        "product", "product_description", "year", "flow", "origin", "destination", "reporter", "partner",
        "quantity_t", "value_eur", "quantity_observation_present", "value_observation_present", "reported_status_flag",
    ])
    write_csv(derived_root / "eu27_raw_selected_observations.csv", raw_records, [
        "product", "product_description", "year", "flow", "reporter", "partner", "origin", "destination",
        "indicator", "obs_value", "obs_status",
    ])
    member_aggregate_rows = sorted(member_aggregate.values(), key=lambda r: (r["product"], r["year"], r["flow"], r["country"], r["partner_aggregate"]))
    write_csv(derived_root / "eu27_member_aggregate_trade.csv", member_aggregate_rows, [
        "product", "product_description", "year", "flow", "country", "partner_aggregate", "quantity_t", "value_eur",
        "quantity_observation_present", "value_observation_present",
    ])

    network: list[dict] = []
    for product in PRODUCTS:
        for year in YEARS:
            edges = [r for r in observations if r["product"] == product and r["year"] == year and r["flow"] == "export"]
            network.append({"product": product, "product_description": PRODUCTS[product], "year": year, **network_metrics(edges)})
    write_csv(derived_root / "eu27_export_network_metrics.csv", network, list(network[0].keys()))

    # Bilateral mirror audit: exports A->B versus imports reported by B from A.
    lookup = {(r["product"], r["year"], r["origin"], r["destination"], r["flow"]): r for r in observations}
    pair_keys = {(r["product"], r["year"], r["origin"], r["destination"]) for r in observations}
    mirrors = []
    for product, year, origin, destination in sorted(pair_keys):
        exp = lookup.get((product, year, origin, destination, "export"))
        imp = lookup.get((product, year, origin, destination, "import"))
        row = {
            "product": product,
            "product_description": PRODUCTS[product],
            "year": year,
            "origin": origin,
            "destination": destination,
            "export_observation_present": exp is not None,
            "import_mirror_observation_present": imp is not None,
            "mirror_status": "both" if exp and imp else "export_only" if exp else "import_only",
            "export_mass_t": exp["quantity_t"] if exp else None,
            "import_mirror_mass_t": imp["quantity_t"] if imp else None,
            "export_value_eur": exp["value_eur"] if exp else None,
            "import_mirror_value_eur": imp["value_eur"] if imp else None,
        }
        if exp and imp and exp["quantity_t"] is not None and imp["quantity_t"] is not None:
            mean_mass = (exp["quantity_t"] + imp["quantity_t"]) / 2
            row["mass_abs_difference_t"] = abs(exp["quantity_t"] - imp["quantity_t"])
            row["mass_relative_abs_difference"] = abs(exp["quantity_t"] - imp["quantity_t"]) / mean_mass if mean_mass else None
        else:
            row["mass_abs_difference_t"] = None
            row["mass_relative_abs_difference"] = None
        if exp and imp and exp["value_eur"] is not None and imp["value_eur"] is not None:
            mean_value = (exp["value_eur"] + imp["value_eur"]) / 2
            row["value_abs_difference_eur"] = abs(exp["value_eur"] - imp["value_eur"])
            row["value_relative_abs_difference"] = abs(exp["value_eur"] - imp["value_eur"]) / mean_value if mean_value else None
        else:
            row["value_abs_difference_eur"] = None
            row["value_relative_abs_difference"] = None
        mirrors.append(row)
    mirror_fields = list(mirrors[0].keys()) if mirrors else ["product", "year", "origin", "destination", "mirror_status"]
    write_csv(derived_root / "eu27_mirror_comparison.csv", mirrors, mirror_fields)

    mirror_summary = []
    for product in PRODUCTS:
        for year in YEARS:
            rows = [r for r in mirrors if r["product"] == product and r["year"] == year]
            both = [r for r in rows if r["mirror_status"] == "both"]
            mirror_summary.append({
                "product": product,
                "product_description": PRODUCTS[product],
                "year": year,
                "directed_pair_year_union": len(rows),
                "both_sides_reported": len(both),
                "export_only": sum(r["mirror_status"] == "export_only" for r in rows),
                "import_only": sum(r["mirror_status"] == "import_only" for r in rows),
                "matched_mass_records": sum(r["mass_relative_abs_difference"] is not None for r in both),
                "median_mass_relative_abs_difference": round(median([r["mass_relative_abs_difference"] for r in both if r["mass_relative_abs_difference"] is not None]), 6) if any(r["mass_relative_abs_difference"] is not None for r in both) else None,
                "sum_export_declarations_mass_t": round(sum(r["export_mass_t"] or 0 for r in rows if r["export_mass_t"] is not None), 6),
            })
    write_csv(derived_root / "eu27_mirror_summary.csv", mirror_summary, list(mirror_summary[0].keys()))

    # Code-level all-period totals use export declarations only; imports are not added to them.
    totals = []
    for product in PRODUCTS:
        period_edges: dict[tuple[str, str], dict] = {}
        for r in observations:
            if r["product"] != product or r["flow"] != "export":
                continue
            route = (r["origin"], r["destination"])
            agg = period_edges.setdefault(route, {"origin": route[0], "destination": route[1], "quantity_t": 0.0, "value_eur": 0.0})
            if r["quantity_t"] is not None:
                agg["quantity_t"] += r["quantity_t"]
            if r["value_eur"] is not None:
                agg["value_eur"] += r["value_eur"]
        edges = list(period_edges.values())
        totals.append({"product": product, "product_description": PRODUCTS[product], "period": "2022-2025", **network_metrics(edges)})
    write_csv(derived_root / "eu27_export_period_totals.csv", totals, list(totals[0].keys()))

    if not reuse_raw:
        (raw_root / "manifest.json").write_text(json.dumps({
            "dataset": "Eurostat Comext DS-045409",
            "retrieved_at_utc": retrieved_at,
            "source_metadata": "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/prefixed-datasets",
            "collection": "annual CN8 product slices, 2022-2025; two trade directions; quantity and value indicators",
            "products": PRODUCTS,
            "eu27_reporter_partner_filter": sorted(EU27),
            "raw_files": raw_manifest,
            "nonzero_status_policy": "No missing or absent observation is converted to zero; all no-row observations remain absent.",
            "classification_boundary": "CN8 classes describe spent accumulators/waste-scrap and sorting status; they do not identify EV use, Li-ion chemistry, or recycling destination.",
            "raw_root": str(raw_root),
            "retrieved_data_version": raw_manifest[0]["dataset_last_update"] if raw_manifest else None,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        (raw_root / "manifest.json").chmod(0o444)

    audit = {
        "retrieved_at_utc": retrieved_at,
        "dataset": "DS-045409",
        "product_code_count": len(PRODUCTS),
        "raw_api_response_count": len(raw_manifest),
        "raw_bytes_total": sum(m["bytes"] for m in raw_manifest),
        "eu27_directed_trade_rows": len(observations),
        "eu27_member_aggregate_trade_rows": len(member_aggregate_rows),
        "rows_without_mass": sum(r["quantity_t"] is None for r in observations),
        "rows_without_value": sum(r["value_eur"] is None for r in observations),
        "interpretation_guard": "Reported goods-trade observations; not EV-only, not observed treatment-facility intake, and not a complete waste-shipment register.",
        "raw_snapshot_manifest": str(raw_root / "manifest.json"),
    }
    (derived_root / "audit_summary.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"Derived tables: {derived_root}")
    print(f"Immutable source snapshot: {raw_root}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=Path(r"F:\AcademicData\project19\raw\eucomext_battery_waste_trade_20260929_v1"))
    parser.add_argument("--derived-root", type=Path, default=Path(r"D:\MLWork\project19\datasets\eucomext_battery_waste_trade_20260929_v2"))
    parser.add_argument("--reuse-raw", action="store_true", help="Reprocess an existing hash-verified immutable raw snapshot without network calls.")
    args = parser.parse_args()
    run(args.raw_root, args.derived_root, reuse_raw=args.reuse_raw)


if __name__ == "__main__":
    main()
