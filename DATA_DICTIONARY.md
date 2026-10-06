# Data dictionary

Encoding: UTF-8 with or without BOM; CSV empty numeric cell means missing, not zero. Boolean fields use `True`/`False`. The release manifest identifies row count, source family, permissions and SHA-256 for every CSV.

## Comext directed observations

Key: `product, year, flow, origin, destination`. `product`: six CN8 codes listed in the request manifest, not battery chemistry or EV application. `year`: 2022–2025. `flow`: `export` or `import`; `reporter, partner`: source direction; `origin, destination`: shipment orientation harmonised to the two reporting views. `quantity_t`: reported tonnes (= source 100 kg ×0.1); `value_eur`: reported euros. `quantity_observation_present, value_observation_present`: numeric availability flags. `reported_status_flag`: original source flag. No absent mirror becomes a zero. `product_description`: credited commodity classification, not an eligibility truth label.

The companion member-aggregate table uses `country` and `partner_aggregate` (`intra_eu27` or `extra_eu27`) rather than bilateral origin/destination. Mirror/diagnostic CSV field names distinguish observation counts, matched keys, mass denominators, weights and undefined quantities. Their estimand is declaration agreement/coverage, not physical-flow accuracy.

## UBA extracted table rows

`origin, destination, year`: NL or BE→DE, 2023/2024. `low_code, basel_code, r_code`: printed waste and operation codes. `description`: waste category, not EV identity. `quantity_t`: **rounded printed** source quantity; `page, raw_line`: source locator. `evidence_grade`: national administrative report. Printed UBA quantities are not substituted for the more precise Basel records; concordance is not independent validation. Extraction changes are explicitly credited to the study authors.

## ILT public permit subset

`notification_id`: public decision reference, may repeat across decisions. `application_type, decision, decision_date`: application/status/date. `notifier_country_source, processor_country_source`: source codes; `NLD`=Netherlands, `DUI`=Germany (not ISO DEU). `waste_description, OECD_code, Basel_code, LoW_code, D_R_codes`: reported scope. `planned_tonnes, planned_shipments, planned_first_departure, planned_last_departure`: planned authorisation fields, **not** received flows or annual production. Numeric planning fields remain source strings where necessary. No company names, addresses, email, telephone or contact/person fields are extracted. Do not aggregate quantities across versions/years as realised shipments.

## Main outputs generated locally, not redistributed

`finite_report_scope_bounds.csv`: route/year/target/stage; `lower_t, upper_t, width_t`; gross declaration denominator; reduction percentages; conditional bound type. Targets are `lithium_family` (exact report label) or lithium-based `EV`; stages `all` or `R4`. `route_rank_identification.csv`: conditional strict-order margin. `decision_certificates.csv`: four year-stage certificates and critical label-discount fraction. `assumption_sensitivity.csv`: all 160 combinations of label relaxation and quantity perturbation, margin and strict-order Boolean. `sequential_scope_ablation.csv`: 16 gross/chemistry/stage/description intervals. `counterfactual_input_errors.csv`: four conditional mapping errors, not observed operator errors. `naive_scope_mapping_feasibility.csv`: compatibility of a joint same-population/exact-counting assumption, not accuracy ranking of reporting sources. `administrative_concordance.csv`: locally reconstructed same-report group check, withheld from redistribution.
