# Public release audit — 5 October 2026

This records the local verification of a GitHub/Zenodo **release candidate**, not a Zenodo deposition. On 6 October 2026, the owner declared **junjiezhang** as the sole real human contributor. The source collection was subsequently uploaded to https://github.com/williamjay1/project19-battery-waste-inputs; the actual URL is now recorded. No tag, Release or archival DOI exists. The owner will personally perform the Zenodo connection. The local candidate/fresh archive both passed 78 tests and all 34 CSV replay checks before upload; source science verification below remains the 5 October record, not new physical evidence.

## Executed checks

- A separate curated directory, without the manuscript or historical private ZIPs, was used for testing and replay.
- Offline inventory/CSV-schema/source-condition checks passed for the supplied code and data.
- Frozen-source replay regenerated **17 main CSVs and 17 retained trade-result CSVs**, all byte-identical to the study's references. Raw inputs were unchanged.
- A separate Decimal checker performed **208 checks**, retaining all **160** assumption cases: **119 strict and 41 non-strict**. This is computational verification, not physical validation.
- Actual anonymous official re-downloads of UBA 2023, UBA 2024 and ILT matched their frozen byte hashes.
- Newly navigated Basel Table 5 HTML pages had different dynamic envelopes but the **same selected scientific-content fingerprints**. Explicit stable-content-mode replay reproduced the same 34 CSV fingerprints. This is an audited navigation-envelope difference, not a silent data replacement.
- Four plots regenerated using source outputs; PDF/SVG/EPS and native 1200-dpi PNG/TIFF generation completed. These generated figures stay local under the data-reuse policy. The existing inspected manuscript/figure PDFs are preserved, not overwritten or republished by this package.
- Synthetic tests cover missing/invalid numbers, code/stage exclusions, mirror direction, ORCID checksums, refusal of fictitious metadata, personal-field exclusion, rejection of edit/non-readonly viewer URLs, and distinguishing HTML-envelope changes from changed source quantities.

Machine-readable per-file inventory is `release_manifest.json`; source/replay fingerprints are in `provenance/source_inputs.json`. Run the supplied commands to create **your own** audit logs. Authors' full logs remain local because they include source paths and/or restricted generated outputs; a summary here does not pretend to archive those sources publicly. Test count and current package hash are recorded in the delivered release QA report.

## Permission and release boundaries

Basel raw/reconstructed and Basel-derived numerical/display files are withheld conservatively. Eurostat retains the Austria-declared CN8 commercial-use exception. UBA extracts are changed numeric data with source credit; ILT extracts contain no retained names, contacts or addresses. Original software is MIT; vendor files retain Apache/MIT notices. No package-wide unrestricted data licence is claimed.

No source science result, main manuscript text, scientific claim or approved PDF changed for this source upload. The public collection excludes old LP projects and internal peer-review/decision files. Reviewer anonymity and genuine authorship/conflict/funding declarations remain the author's submission responsibilities. GitHub upload was authorised by the user and completed using the existing authenticated CLI session. No Zenodo API operation, DOI reservation or information-access request was performed. Analysis/replay scripts do not upload data or operate accounts.
