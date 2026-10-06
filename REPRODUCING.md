# Reproducing the study

## Levels of verification

1. `python -m tools.verify_release --output reproduction/offline_audit.json`: offline package integrity, privacy schema and declared data coverage. This checks supplied files, not withheld source truth.
2. `python -m pytest -q`: synthetic edge-case regression tests. These are not scientific samples.
3. `python -m tools.reproduce --raw-root RAW --output NEW_OUTPUT`: actual source-to-result replay with immutable raw snapshots. It regenerates all 17 main CSVs, compares their byte fingerprints and independently recomputes intervals using Decimal without importing production eligibility functions. It also regenerates retained trade diagnostics.
4. `python -m tools.figures --results NEW_OUTPUT --output NEW_FIGURES --high-res`: four vector plots plus native 1200-dpi PNG/TIFF, using all 160 sensitivity cases. View every figure before using it in an article.

## Raw files to obtain

`provenance/source_inputs.json` lists URLs, observed SHA-256, retrieval dates and relative paths for the six inputs. Do not put raw files in GitHub, add them to `.gitignore`, or overwrite prior snapshots. Obtain UBA and ILT files with the optional downloader:

```text
python -m tools.fetch_sources --raw-root /path/to/new/raw --sources uba2023 uba2024 permits
```

The downloader checks official HTTPS hostnames, writes exclusively new files, keeps timestamps/fingerprints and reports upstream changes. It does not use login, personal credentials or paid APIs. Basel collection is a separate explicit command after reading its terms:

```text
python src/capture_basel_readonly_table5.py --raw /path/to/raw/basel_table5_navigation_20261002_v1 --year 2023 --url "https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&surveyid=86&voterid=62482&readonly=1&nomenu=1"
python src/capture_basel_readonly_table5.py --raw /path/to/raw/basel_table5_transfer_20261002_v1 --year 2024 --url "https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&surveyid=89&voterid=64675&readonly=1&nomenu=1"
```

Only the public read-only viewer's Table 5 navigation is used. No answers, report-save or submission actions are sent. Rate is two requests per report, with no bulk harvesting. Raw HTML contains dynamic navigation state, so a newly fetched page may differ bytewise. Default replay requires the original six byte fingerprints. The explicit `--allow-stable-basel-content` mode permits a changed **Basel HTML envelope only** if every selected scientific row has the same frozen canonical fingerprint; it records the changed raw hash and unchanged scientific-content hash. It is not a licence acceptance proxy or a silent new data vintage. Any selected-row change aborts. UBA/ILT snapshot changes abort the frozen replay; keep the new version and audit separately.

The 980-row credited Comext input is supplied under the accompanying source conditions. The original two 24-request API manifests are in `provenance/comext_request_manifests.json`. To re-extract a frozen Comext raw snapshot, use `src/comext_trade_audit.py` with **explicit** `--raw-root`, `--derived-root`, `--reuse-raw`; `src/verify_comext_raw_extraction.py` independently verifies orientation, units, missingness and coverage. An anonymous current API refresh is a **new vintage**, not the frozen input. The API may revise historical values: never silently substitute it.

## Outputs and preservation

Choose a new work-output path for every replay; directories are never recursively deleted or overwritten. `replay_audit.json` reports executed commands, compared CSV count, independent checks, package versions and whether raw files changed. Locally regenerated Basel-derived outputs and all raw sources stay out of the repository. Source processing logs remain in that local output, not in the public release.

The source manifest's reference results are SHA-256 fingerprints, not released copies of withheld data. A fingerprint cannot recover a missing source file. Full replay is limited by upstream version availability; this is stated rather than concealed by a claim of fully archived raw evidence.
