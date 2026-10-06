"""Nature-inspired, source-constrained vector displays for the IJEST article.

Only the rendering changes. Published interval outputs are not re-estimated.
Nature Figure skill auditors are used under Apache-2.0; SciencePlots under MIT.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scienceplots  # registers the SciencePlots styles
from matplotlib import font_manager
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.transforms import ScaledTranslation
from PIL import Image
from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "src/vendor/nature_figure"
sys.path.insert(0, str(VENDOR))
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = ROOT / "reproduction/figures"
QA = OUT / "qa"
PREVIEWS = OUT / "previews"
WIDTH_MM = 174.0
DISPLAY_PT = 8
FINAL_DPI = 1200
TEAL = "#267D87"
GREY = "#848F9C"
BLUE = "#537BA2"
INK = "#20272E"
STAGE_ORDER = ["unqualified_A1170", "known_chemistry_exclusion",
               "plus_reported_R4", "plus_explicit_lithium_label"]
STAGE_LABELS = ["Gross code", "Chemistry filter", "+ R4 stage", "+ Description"]
RESULTS = ROOT / "reproduction/results"
FILES = {
    "ablation": RESULTS / "scope_decision_certificates_20261002_v1/sequential_scope_ablation.csv",
    "pressure": RESULTS / "scope_decision_certificates_20261002_v1/assumption_sensitivity.csv",
    "certificates": RESULTS / "scope_decision_certificates_20261002_v1/decision_certificates.csv",
    "bounds2023": RESULTS / "scope_identification_pilot_20261002_v1/finite_report_scope_bounds.csv",
    "bounds2024": RESULTS / "scope_identification_transfer_20261002_v1/finite_report_scope_bounds.csv",
    "population": RESULTS / "scope_identification_pilot_20261002_v1/naive_scope_mapping_feasibility.csv",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str) -> Decimal:
    """Never silently reinterpret missing or invalid source cells as zero."""
    if value is None or not str(value).strip():
        raise ValueError("Missing numerical source cell")
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"Invalid numerical source cell: {value!r}") from error
    if not result.is_finite():
        raise ValueError(f"Non-finite numerical source cell: {value!r}")
    return result


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def one(rows: list[dict], **conditions) -> dict:
    selected = [r for r in rows if all(str(r[k]) == str(v) for k, v in conditions.items())]
    if len(selected) != 1:
        raise ValueError(f"Expected one source row for {conditions}; found {len(selected)}")
    return selected[0]


def style():
    # Portable: never redistribute or require commercial Windows fonts.
    known = {item.name for item in font_manager.fontManager.ttflist}
    font = "Arial" if "Arial" in known else "DejaVu Sans"
    plt.style.use(["science", "no-latex", str(VENDOR / "nature.mplstyle")])
    plt.rcParams.update({
        "font.family":"sans-serif", "font.sans-serif":[font], "text.usetex":False,
        "pdf.fonttype":42,"ps.fonttype":42,"pdf.use14corefonts":False,"svg.fonttype":"none",
        "font.size":DISPLAY_PT,"axes.titlesize":DISPLAY_PT,"axes.labelsize":DISPLAY_PT,
        "xtick.labelsize":DISPLAY_PT,"ytick.labelsize":DISPLAY_PT,"legend.fontsize":DISPLAY_PT,
        "text.color":INK,"axes.labelcolor":INK,"axes.edgecolor":INK,
        "xtick.color":INK,"ytick.color":INK,"axes.spines.top":False,"axes.spines.right":False,
        "axes.grid":False,"xtick.top":False,"ytick.right":False,"xtick.minor.visible":False,
        "ytick.minor.visible":False,"xtick.direction":"out","ytick.direction":"out",
        "axes.linewidth":.6,"lines.linewidth":1.2,"savefig.facecolor":"white",
        "savefig.edgecolor":"white","figure.facecolor":"white","savefig.bbox":None})
    return font


def panel_heading(fig, ax, letter: str, title: str):
    transform = ax.transAxes + ScaledTranslation(-10/72, 7/72, fig.dpi_scale_trans)
    ax.text(0, 1, letter, transform=transform, fontweight="bold", fontsize=8,
            ha="right", va="bottom", clip_on=False)
    ax.set_title(title, loc="left", pad=8, fontweight="normal")


def interval(ax, y: float, lower: float, upper: float, colour: str):
    if not (math.isfinite(lower) and math.isfinite(upper) and 0 <= lower <= upper):
        raise ValueError("Invalid interval geometry")
    ax.plot([lower, upper], [y, y], color=colour, linewidth=2.0, solid_capstyle="butt")
    ax.plot([lower, lower], [y-.095, y+.095], color=colour, linewidth=0.8)
    if upper != lower:
        ax.plot([upper, upper], [y-.095, y+.095], color=colour, linewidth=0.8)
    else:
        ax.plot(lower, y, marker="s", markersize=3, color=colour, linestyle="none")


def export_csv(stem: str, rows: list[dict]):
    with (OUT / f"{stem}.source_data.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export(fig, stem: str, *, aligned=True, panels=None, high_res=True) -> dict:
    fig.canvas.draw()
    if aligned:
        require_matplotlib_panel_alignment(
            fig, json_out=QA / f"{stem}.alignment.json",
            overlay_svg=QA / f"{stem}.alignment.svg", require_panel_labels=True,
            panel_ids=panels, strict=True,
        )
    else:
        (QA / f"{stem}.alignment.json").write_text(json.dumps({
            "verdict": "NOT APPLICABLE", "reason": "Single table, not comparable plot panels",
        }, indent=2), encoding="utf-8")
    # Exact final dimensions: no tight cropping, upsampling, or rasterized marks.
    fig.savefig(OUT / f"{stem}.pdf", format="pdf", metadata={"Title": stem, "Author": ""})
    fig.savefig(OUT / f"{stem}.svg", format="svg", metadata={"Title": stem, "Creator": "Matplotlib"})
    fig.savefig(OUT / f"{stem}.eps", format="eps")
    fig.savefig(PREVIEWS / f"{stem}.png", dpi=300)
    if high_res:
        fig.savefig(OUT / f"{stem}.png", dpi=FINAL_DPI)
        fig.savefig(OUT / f"{stem}.tiff", dpi=FINAL_DPI,
                    pil_kwargs={"compression": "tiff_lzw"})
    report = {
        "stem": stem, "width_mm": round(fig.get_figwidth() * 25.4, 5),
        "height_mm": round(fig.get_figheight() * 25.4, 5), "raster_dpi": FINAL_DPI if high_res else None,
        "pdf_sha256": digest(OUT / f"{stem}.pdf"),
    }
    if high_res:
        with Image.open(OUT / f"{stem}.png") as image:
            report["raster_pixels"] = list(image.size)
            report["png_dpi_metadata"] = list(image.info.get("dpi", []))
            expected = [int(fig.get_figwidth() * FINAL_DPI), int(fig.get_figheight() * FINAL_DPI)]
            if max(abs(a-b) for a, b in zip(expected, image.size)) > 1:
                raise ValueError("Native raster pixel dimensions do not match physical size")
    plt.close(fig)
    return report


def figure1(high_res=True):
    rows = load_csv(FILES["ablation"])
    if len(rows) != 16:
        raise ValueError("Scope progression must retain all 16 route-year-stage outputs")
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH_MM/25.4, 126/25.4))
    fig.subplots_adjust(left=.225, right=.975, bottom=.13, top=.91, wspace=.90, hspace=.76)
    source = []
    for ax, (year, origin), letter in zip(axes.flat, [(2023, "NL"), (2023, "BE"), (2024, "NL"), (2024, "BE")], "abcd"):
        gross = number(one(rows, year=year, origin=origin, level=STAGE_ORDER[0])["upper_t"])
        if gross <= 0:
            raise ValueError("Normalisation requires a positive gross declaration")
        for i, level in enumerate(STAGE_ORDER):
            r = one(rows, year=year, origin=origin, level=level)
            lower, upper = number(r["lower_t"]), number(r["upper_t"])
            lp, up = float(100*lower/gross), float(100*upper/gross)
            interval(ax, 3-i, lp, up, [GREY, GREY, BLUE, TEAL][i])
            source.append({**r, "gross_denominator_t": str(gross),
                           "lower_percent_of_gross": lp, "upper_percent_of_gross": up})
        ax.set_ylim(-.45, 3.65)
        ax.set_xlim(-2, 104)
        ax.set_yticks(range(4), labels=STAGE_LABELS[::-1])
        ax.tick_params(axis="y", length=0, pad=4)
        ax.spines["left"].set_visible(False)
        ax.set_xticks([0, 50, 100])
        ax.set_xlabel("Share of gross A1170 (%)", labelpad=4)
        country = {"NL": "Netherlands", "BE": "Belgium"}[origin]
        panel_heading(fig, ax, letter, f"{country}, {year}")
        ax.text(0, 3.48, f"Gross: {float(gross):,.3f} t", va="center", fontsize=DISPLAY_PT)
    fig.text(.5, .025, "Scope intervals within selected declarations; not confidence intervals", ha="center", fontsize=DISPLAY_PT)
    export_csv("fig1_scope_progression", source)
    return export(fig, "fig1_scope_progression", panels=list("abcd"), high_res=high_res)


def figure2(high_res=True):
    rows = load_csv(FILES["bounds2023"]) + load_csv(FILES["bounds2024"])
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_MM/25.4, 110/25.4))
    fig.subplots_adjust(left=.185, right=.73, bottom=.13, top=.91, hspace=.98)
    source = []
    for ax, target, letter, heading in zip(axes, ["lithium_family", "EV"], "ab",
                                         ["Lithium-battery-labelled R4 input", "Lithium-based EV traction R4 input"]):
        labels = []
        for i, (year, origin) in enumerate([(2023, "NL"), (2023, "BE"), (2024, "NL"), (2024, "BE")]):
            r = one(rows, year=year, origin=origin, target=target, stage="R4")
            lower, upper = float(number(r["lower_t"])), float(number(r["upper_t"]))
            y = 3-i
            interval(ax, y, lower, upper, TEAL if origin == "NL" else GREY)
            labels.append(f"{origin}, {year}")
            ax.text(1.055, y, f"[{lower:,.3f}, {upper:,.3f}]", transform=ax.get_yaxis_transform(),
                    clip_on=False, ha="left", va="center", fontsize=DISPLAY_PT)
            source.append(r)
        ax.set_xlim(-40, 2500)
        ax.set_ylim(-.45, 3.65)
        ax.set_xticks([0, 500, 1000, 1500, 2000, 2500])
        ax.set_yticks(range(4), labels=labels[::-1])
        ax.tick_params(axis="y", length=0, pad=5)
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("Declared input (t)", labelpad=4)
        panel_heading(fig, ax, letter, heading)
        ax.text(1.055, 3.52, "[Lower, upper] (t)", transform=ax.get_yaxis_transform(),
                ha="left", va="bottom", clip_on=False, fontsize=DISPLAY_PT)
    fig.text(.5, .025, "Missing application evidence retains zero EV lower amounts", ha="center", fontsize=DISPLAY_PT)
    export_csv("fig2_input_identification", source)
    return export(fig, "fig2_input_identification", panels=list("ab"), high_res=high_res)


def figures1(high_res=True):
    rows = load_csv(FILES["pressure"])
    if len(rows) != 160:
        raise ValueError("All 160 pressure combinations must be displayed")
    discounts = [Decimal(str(x)) for x in [0, .25, .5, .75, .9, .95, .99, 1]]
    errors = [Decimal(str(x)) for x in [0, .01, .05, .1, .25]]
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH_MM/25.4, 130/25.4))
    fig.subplots_adjust(left=.105, right=.98, bottom=.17, top=.91, wspace=.44, hspace=.65)
    retained, strict = [], 0
    for ax, (year, stage), letter in zip(axes.flat, [(2023,"all"),(2023,"R4"),(2024,"all"),(2024,"R4")], "abcd"):
        state = np.zeros((len(errors), len(discounts)))
        for i, error in enumerate(errors):
            for j, discount in enumerate(discounts):
                matches = [r for r in rows if r["year"] == str(year) and r["stage"] == stage
                           and number(r["quantity_error"]) == error and number(r["label_relaxation"]) == discount]
                if len(matches) != 1:
                    raise ValueError("Non-unique robustness grid cell")
                r = matches[0]
                margin = number(r["margin_t"])
                is_strict = margin > 0
                if is_strict != (r["NL_strictly_above_BE"] == "True"):
                    raise ValueError("Margin and strict-order flag disagree")
                state[i,j] = 2 if is_strict else (1 if margin == 0 else 0)
                ax.text(j+.5, i+.5, "+" if is_strict else ("0" if margin == 0 else "−"),
                        ha="center", va="center", fontsize=DISPLAY_PT)
                strict += int(is_strict)
                retained.append({**r, "display_state": "strict" if is_strict else ("equality" if margin == 0 else "negative")})
        ax.pcolormesh(np.arange(9), np.arange(6), state,
                      cmap=ListedColormap(["#DDB7AE", "#EBEEF0", "#B8DADD"]),
                      vmin=0, vmax=2, shading="flat", edgecolors="none", zorder=0, rasterized=False)
        ax.set_xlim(0, 8); ax.set_ylim(0, 5)
        ax.set_xticks(np.arange(8)+.5, labels=[f"{int(d*100)}" for d in discounts])
        ax.set_yticks(np.arange(5)+.5, labels=[f"{int(e*100)}" for e in errors])
        ax.tick_params(length=2)
        ax.set_xlabel("Tested lower-mass discount (%)", labelpad=5)
        ax.set_ylabel("Tested quantity perturbation (%)", labelpad=5)
        panel_heading(fig, ax, letter, f"{year}, {'all operations' if stage == 'all' else 'R4 only'}")
    if strict != 119:
        raise ValueError(f"Pressure result unexpectedly changed: {strict} strict cells")
    fig.text(.5, .065, "+ Strict Dutch > Belgian order     0 Equality     − Negative margin", ha="center", fontsize=DISPLAY_PT)
    fig.text(.5, .025, "160 tested cases: 119 strict, 41 non-strict; categorical cell spacing", ha="center", fontsize=DISPLAY_PT)
    export_csv("figS1_ordering_pressure_grid", retained)
    return export(fig, "figS1_ordering_pressure_grid", panels=list("abcd"), high_res=high_res)


def figures2(high_res=True):
    rows = load_csv(FILES["population"])
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_MM/25.4, 104/25.4))
    fig.subplots_adjust(left=.31, right=.755, bottom=.145, top=.91, hspace=1.08)
    source = []
    for ax, origin, limit, letter in zip(axes, ["NL", "BE"], [5000, 2.2], "ab"):
        exported = one(rows, origin=origin, CN_scope="six_CN8", view="export", stage="all")
        imports = [r for r in rows if r["origin"] == origin and r["CN_scope"] == "six_CN8"
                   and r["view"] == "import" and r["stage"] == "all"]
        if len(imports) > 1:
            raise ValueError("Duplicated import population row")
        values = [float(number(exported["hypothetical_CN_upper_t"])),
                  float(number(imports[0]["hypothetical_CN_upper_t"])) if imports else None,
                  float(number(exported["Basel_report_label_lower_t"]))]
        labels = ["Comext exporter", "Comext importer", "Lithium-labelled minimum"]
        for i, (label, value) in enumerate(zip(labels, values)):
            y = 2-i
            if value is not None:
                ax.barh(y, value, height=.32, color=TEAL if i == 2 else GREY, edgecolor="none")
            ax.text(1.065, y, "Unavailable" if value is None else f"{value:,.3f}",
                    transform=ax.get_yaxis_transform(), ha="left", va="center", clip_on=False, fontsize=DISPLAY_PT)
            source.append({"year": 2023, "origin": origin, "destination": "DE", "quantity_definition": label,
                           "value_t": "" if value is None else value,
                           "availability": "unavailable" if value is None else "available",
                           "population_compatible": "not established"})
        ax.set_ylim(-.45, 2.6); ax.set_xlim(0, limit)
        ax.set_yticks(range(3), labels=labels[::-1]); ax.tick_params(axis="y", length=0, pad=5)
        ax.spines["left"].set_visible(False)
        ax.set_xticks([0, 1000, 2000, 3000, 4000, 5000] if origin == "NL" else [0, .5, 1, 1.5, 2])
        ax.set_xlabel("Reported quantity (t)", labelpad=5)
        panel_heading(fig, ax, letter, f"{'Netherlands' if origin == 'NL' else 'Belgium'} to Germany, 2023")
        ax.text(1.065, 2.46, "Amount (t)", transform=ax.get_yaxis_transform(),
                ha="left", va="bottom", clip_on=False, fontsize=DISPLAY_PT)
    fig.text(.5, .025, "Different panel scales; declaration populations are not interchangeable", ha="center", fontsize=DISPLAY_PT)
    export_csv("figS2_population_compatibility", source)
    return export(fig, "figS2_population_compatibility", panels=list("ab"), high_res=high_res)


def main():
    global OUT, QA, PREVIEWS, FILES
    p=argparse.ArgumentParser(description="Four source-constrained vector figures; no new estimates")
    p.add_argument("--results",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--high-res",action="store_true")
    args=p.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    OUT=args.output.resolve(); QA=OUT/"qa"; PREVIEWS=OUT/"previews"
    FILES={key:args.results/path.relative_to(RESULTS) for key,path in FILES.items()}
    OUT.mkdir(parents=True); QA.mkdir(); PREVIEWS.mkdir()
    font=style()
    reports=[fn(high_res=args.high_res) for fn in [figure1,figure2,figures1,figures2]]
    (OUT/"figure_manifest.json").write_text(json.dumps({"font":font,"figures":reports,
        "type":"vector PDF/SVG/EPS; optional native 1200-dpi rasters",
        "restricted_outputs":"locally generated; not automatically permission-cleared for redistribution",
        "visual_approval":"inspect regenerated figures; original article approval is not inherited"},indent=2),encoding="utf-8")
    print(json.dumps({"status":"GENERATED","figures":len(reports),"font":font}))

if __name__=="__main__": main()
