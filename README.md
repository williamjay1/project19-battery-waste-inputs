# Battery-waste recycling input identification

Reproducibility software for **Scope-constrained identification of battery-waste recycling inputs from European public records** (target: International Journal of Environmental Science and Technology, Original Paper).

This repository reproduces *report-conditioned input intervals*, conditional route-ordering certificates and deterministic assumption stresses. It does not estimate actual EV battery shipments, plant receipts, recovered metal, facility capacity or an EU-wide physical supply. A1170 is not an EV or lithium-only code; a lithium description does not identify EV application; R4 is a declared treatment operation, not recovered output. Basel and UBA share a national reporting basis. ILT decisions concern planned authorisations, not realised receipts.

## What is included

- Executed analysis code and unit tests, including missing-value, code/stage exclusion, mirror orientation and decision-boundary tests.
- The frozen 980-row EU-27 Comext derived input and retained trade diagnostics, **under Eurostat source-specific terms, not the software MIT licence**. Austria-declared CN8 observations retain the commercial-use restriction.
- Credited UBA numeric extracts and 151 ILT non-personal permit decision records. Names, addresses, contacts, raw ODS and company fields are not included.
- Source URLs, acquisition instructions, byte/semantic fingerprints, a field dictionary, environment versions and per-file checksums.
- Portable generation of four vector figures and optional native 1200-dpi rasters from locally reproduced outputs.

Basel HTML, reconstructed Basel source tables **and Basel-derived result/display CSVs** are withheld from this public release because the website terms do not grant general redistribution/derivative-work permission. The code generates those files locally from sources obtained for permitted inspection. There is no claim that the repository contains an unrestricted full data release. Raw publisher pages, manuscript/PDF, editorial working files, credentials, Windows fonts and historical EV optimisation projects are excluded. Existing private delivery archives must not be added to this repository.

## Install and run

Python 3.12 is the locally tested interpreter. Other versions/platforms are not claimed as tested. Use a new virtual environment:

```text
python -m venv .venv
python -m pip install -r requirements.txt
python -m pytest -q
python -m tools.verify_release --output reproduction/offline_audit.json
```

Activate the virtual environment before installing (Windows: `.venv\Scripts\activate`; macOS/Linux: `source .venv/bin/activate`). All `python` commands refer to that environment. `requirements.txt` pins the top-level versions actually used; `environment_observed.json` records the executed environment. It is not a universal lock or a claim of a fresh pip installation on every operating system.

The offline audit checks the release manifest, privacy schema and available data. **It does not independently verify the withheld raw Basel evidence.** Unit-test fixtures are synthetic edge cases, never scientific observations.

For a full source-to-result replay, obtain the primary sources following [REPRODUCING.md](REPRODUCING.md), then run:

```text
python -m tools.reproduce --raw-root /path/to/local/raw --output /path/to/new/work-output
```

On the authors' machine raw snapshots are read-only on F: and outputs on D:. Both arguments are explicit; these drives are not required elsewhere. Raw sources are never overwritten. Outputs must be a new directory. The replay compares all 17 result CSV fingerprints, independently recomputes intervals with Decimal, and preserves all 160 pressure cases (119 strict and 41 non-strict). It also recreates the retained 80 trade diagnostics and the 2025 temporal comparison without using the holdout for selection.

To regenerate figures after the replay:

```text
python -m tools.figures --results /path/to/new/work-output --output /path/to/new/figures --high-res
```

PDF/SVG/EPS are vectors; dpi applies only to PNG/TIFF. The four-figure script uses an installed Arial font when available and Matplotlib's bundled DejaVu Sans otherwise; no commercial font files are shipped. Different fonts may change geometry: inspect regenerated figures before use. The already inspected article figures are not reissued as a public data release here.

## Licences, citation and release

Original software is MIT. **Data are not covered by MIT.** See [DATA_REUSE.md](DATA_REUSE.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the licence class of each file in `release_manifest.json`. UBA/ILT/Eurostat do not endorse this study or its transformations. External data restrictions are not removed by GitHub or Zenodo archiving.

The project owner declares **junjiezhang** as the sole real human contributor; this exact undivided name appears in [CONTRIBUTORS.json](CONTRIBUTORS.json), [CITATION.md](CITATION.md) and `.zenodo.json`. No institution, ORCID, surname/given-name split, funding or journal acceptance is inferred. AI assistance and human responsibility are disclosed in [AI_USE.md](AI_USE.md) and [AUTHORSHIP.md](AUTHORSHIP.md). Third-party source/tool credit is not additional project authorship.

Public source repository: [williamjay1/project19-battery-waste-inputs](https://github.com/williamjay1/project19-battery-waste-inputs). The GitHub account hosts the code; the sole declared real human contributor remains **junjiezhang**. This is a source snapshot, not a formal tagged release, journal publication or Zenodo deposit. No DOI has been assigned. `CITATION.md` is used rather than guessed CFF personal-name fields. The owner will personally connect Zenodo before creating a formal GitHub release; verify the deposited files/metadata, then cite the exact **version DOI**. Do not silently replace a published release. See [GITHUB_PUBLICATION.md](GITHUB_PUBLICATION.md) and [ZENODO_HANDOFF_CN.md](ZENODO_HANDOFF_CN.md).

See [CITATION.md](CITATION.md), [SCIENTIFIC_BOUNDARY.md](SCIENTIFIC_BOUNDARY.md) and [DATA_DICTIONARY.md](DATA_DICTIONARY.md). No external publication or upload is performed by any script in this repository.
