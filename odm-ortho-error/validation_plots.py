#!/usr/bin/env python3
"""Generate validation plots for the ODM ortho-error investigation.

Reads per-point data from aztec10 (v3.6.0-baseline, unpatched) and aztec11
(v3.6.0-projected, PRs #48 + #2008 applied) rmse outputs, produces:

  images/aztec_validation_ortho_vs_distance.svg
      Overlay of ortho_dH vs distance from rasterizer origin for both runs.
      Baseline shows U-shape; patched is flat.

  images/aztec_validation_overview_baseline.png
      Scatter map colored by ortho_dH — baseline (aztec10).

  images/aztec_validation_overview_patched.png
      Scatter map colored by ortho_dH — patched (aztec11).

Run from the geo conda env:

  conda run -n geo python validation_plots.py

Inputs (hardcoded for now):
  ~/stratus/aztec10/rmse.html  + rmse.json
  ~/stratus/aztec11/rmse.html  + rmse.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

JOBS = {
    "baseline_utm": {
        "label":      "aztec10 — v3.6.0 baseline, UTM 32613",
        "dir":        Path.home() / "stratus" / "aztec10",
        "json_src":   "self",
        "survey_crs": "EPSG:32613",
        "color":      "#D1495B",
    },
    "baseline_6528": {
        "label":      "aztec12 — v3.6.0 baseline, state plane 6528",
        "dir":        Path.home() / "stratus" / "aztec12",
        "json_src":   "self",
        "survey_crs": "EPSG:6528",
        "color":      "#E28E2E",
    },
    "pix4d": {
        "label":      "aztec7/pix4d — reference",
        "dir":        Path.home() / "stratus" / "aztec7" / "pix4d",
        # Pix4D was run in ortho-only mode (no reconstruction JSON). Borrow
        # survey coords from aztec11 — same control points, identical labels.
        "json_src":   Path.home() / "stratus" / "aztec11" / "rmse.json",
        "survey_crs": "EPSG:32613",
        "color":      "#1F77B4",
    },
    "patched_utm": {
        "label":      "aztec11 — v3.6.0 + PRs #48 + #2008, UTM 32613",
        "dir":        Path.home() / "stratus" / "aztec11",
        "json_src":   "self",
        "survey_crs": "EPSG:32613",
        "color":      "#2E7D5B",
    },
    "patched_6528": {
        "label":      "aztec13 — v3.6.0 + PRs #48 + #2008, state plane 6528",
        "dir":        Path.home() / "stratus" / "aztec13",
        "json_src":   "self",
        "survey_crs": "EPSG:6528",
        "color":      "#5B2E7D",
    },
}

# UTM 13N offsets from reconstruction.topocentric.json reference_lla (36.9022, -107.9193).
# Same for both jobs (same flight corridor).
UTM_EAST_OFFSET  = 239890.0
UTM_NORTH_OFFSET = 4088006.0

OUT_DIR = Path(__file__).parent / "images"


# Per-point table rows come in two flavours:
#
# A) ODM reconstruction + ortho (aztec10/aztec11):
#    <tr><td><a>LABEL</a></td><td>ROLE</td><td>N_IMAGES</td>
#        <td>dH</td><td>dZ</td><td>d3D</td><td>ortho_dH <span>...</span></td></tr>
#
# B) Ortho-only (aztec7/pix4d — no reconstruction JSON supplied):
#    <tr><td><a>LABEL</a></td><td>ROLE</td><td>ortho_dH <span>...</span></td></tr>
ROW_RE_RECON = re.compile(
    r'<tr><td><a[^>]*>([A-Z]+-[A-Za-z0-9\-]+)</a></td>'
    r'<td>(GCP|CHK)</td>'
    r'<td>(\d+)</td>'
    r'<td>([+\-]?[\d\.]+)</td>'
    r'<td>([+\-]?[\d\.]+)</td>'
    r'<td>[+\-]?[\d\.]+</td>'
    r'<td>([+\-]?[\d\.]+)\s*<span',
)
ROW_RE_ORTHO_ONLY = re.compile(
    r'<tr><td><a[^>]*>([A-Z]+-[A-Za-z0-9\-]+)</a></td>'
    r'<td>(GCP|CHK)</td>'
    r'<td>([+\-]?[\d\.]+)\s*<span',
)


def parse_html_per_point(html_path: Path) -> dict[str, dict]:
    """Return {label: {role, recon_dH, recon_dZ, ortho_dH, n_images}} — handles both formats."""
    html = html_path.read_text()
    out: dict[str, dict] = {}
    for m in ROW_RE_RECON.finditer(html):
        label, role, n_imgs, recon_dh, recon_dz, ortho_dh = m.groups()
        out[label] = {
            "role":     role,
            "n_images": int(n_imgs),
            "recon_dH": float(recon_dh),
            "recon_dZ": float(recon_dz),
            "ortho_dH": float(ortho_dh),
        }
    if not out:
        # Ortho-only file — no reconstruction columns.
        for m in ROW_RE_ORTHO_ONLY.finditer(html):
            label, role, ortho_dh = m.groups()
            out[label] = {
                "role":     role,
                "n_images": None,
                "recon_dH": None,
                "recon_dZ": None,
                "ortho_dH": float(ortho_dh),
            }
    return out


def merge_with_json(per_point: dict, rmse_json: Path, survey_crs: str) -> list[dict]:
    """Add survey_x/y/z + reconstruction dX/dY from rmse.json. Normalises survey
    coords to UTM 32613 metres so the x-axis |northing - utm_north_offset| is
    consistent across runs with different working CRSes."""
    data = json.loads(rmse_json.read_text())
    if survey_crs != "EPSG:32613":
        import pyproj
        to_utm = pyproj.Transformer.from_crs(survey_crs, "EPSG:32613", always_xy=True)
    else:
        to_utm = None

    merged = []
    for role in ("gcp", "chk"):
        for p in data[role]["points"]:
            lab = p["label"]
            if lab not in per_point:
                continue
            sx, sy = p["survey_x"], p["survey_y"]
            if to_utm is not None:
                sx, sy = to_utm.transform(sx, sy)
            merged.append({
                "label":     lab,
                "role":      per_point[lab]["role"],
                "n_images":  per_point[lab]["n_images"],
                "ortho_dH":  per_point[lab]["ortho_dH"],
                "recon_dH":  per_point[lab]["recon_dH"],
                "recon_dZ":  per_point[lab]["recon_dZ"],
                "survey_x":  sx,   # UTM 32613 metres regardless of source CRS
                "survey_y":  sy,
                "dX":        p.get("dX", 0.0),
                "dY":        p.get("dY", 0.0),
            })
    return merged


def distance_from_origin(points: list[dict]) -> np.ndarray:
    """|northing - utm_north_offset| in metres; matches aztec7 investigation chart."""
    return np.array([abs(p["survey_y"] - UTM_NORTH_OFFSET) for p in points])


def plot_ortho_vs_distance(jobs: dict):
    """Overlaid scatter of ortho_dH vs |dN from origin|, for baseline + patched."""
    fig, ax = plt.subplots(figsize=(8, 5.5))

    for job_key, meta in jobs.items():
        d   = distance_from_origin(meta["points"])
        dh  = np.array([p["ortho_dH"] for p in meta["points"]])
        ax.scatter(d, dh, s=30, alpha=0.75, color=meta["color"],
                   label=meta["label"], edgecolors="white", linewidths=0.5)

    ax.set_xlabel("|northing − utm_north_offset|  (m)")
    ax.set_ylabel("ortho dH  (ft)")
    ax.set_title("Orthophoto horizontal error vs. distance from rasterizer origin\n"
                 "aztec corridor · 41 control points · 1385 DJI M3E images")
    ax.axhline(0, color="grey", linewidth=0.5, alpha=0.5)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    out = OUT_DIR / "aztec_validation_ortho_vs_distance.svg"
    fig.savefig(out)
    plt.close(fig)
    print(f"  wrote {out}")


def plot_overview(jobs: dict):
    """One scatter-map per run, colored by ortho_dH (green → red)."""
    # Shared colour scale across the two panels for honest comparison.
    all_dh = np.concatenate([
        [p["ortho_dH"] for p in meta["points"]] for meta in jobs.values()
    ])
    vmin, vmax = 0.0, float(np.max(all_dh))

    for job_key, meta in jobs.items():
        pts = meta["points"]
        fig, ax = plt.subplots(figsize=(10, 3.5))
        xs = np.array([p["survey_x"] for p in pts]) - UTM_EAST_OFFSET
        ys = np.array([p["survey_y"] for p in pts]) - UTM_NORTH_OFFSET
        dh = np.array([p["ortho_dH"] for p in pts])
        sc = ax.scatter(xs, ys, c=dh, cmap="RdYlGn_r", vmin=vmin, vmax=vmax,
                        s=60, edgecolors="black", linewidths=0.5)
        ax.set_xlabel("easting − utm_east_offset  (m)")
        ax.set_ylabel("northing − utm_north_offset  (m)")
        ax.set_title(f"{meta['label']} — targets colored by ortho dH (ft)")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        plt.colorbar(sc, ax=ax, label="ortho dH (ft)")
        plt.tight_layout()
        out = OUT_DIR / f"aztec_validation_overview_{job_key}.png"
        fig.savefig(out, dpi=120)
        plt.close(fig)
        print(f"  wrote {out}")


def summarise(jobs: dict):
    """Print the summary stats to stdout so the Markdown tables stay honest."""
    print()
    print(f"{'job':<10} {'N':>4} {'mean|dH|':>10} {'median':>8} {'max':>8} {'RMS_H':>8}")
    for job_key, meta in jobs.items():
        dh = np.array([p["ortho_dH"] for p in meta["points"]])
        rms = float(np.sqrt(np.mean(dh ** 2)))
        print(f"{job_key:<10} {len(dh):>4} {np.mean(np.abs(dh)):>10.3f} "
              f"{np.median(dh):>8.3f} {np.max(dh):>8.3f} {rms:>8.3f}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, meta in JOBS.items():
        html_path = meta["dir"] / "rmse.html"
        if not html_path.exists():
            raise SystemExit(f"Missing input: {html_path}")
        per_point = parse_html_per_point(html_path)
        json_path = meta["dir"] / "rmse.json" if meta["json_src"] == "self" else meta["json_src"]
        if not json_path.exists():
            raise SystemExit(f"Missing input: {json_path}")
        meta["points"] = merge_with_json(per_point, json_path, meta.get("survey_crs", "EPSG:32613"))
        print(f"{key}: parsed {len(meta['points'])} points from {html_path.name} "
              f"(coords from {json_path.name})")

    plot_ortho_vs_distance(JOBS)
    plot_overview(JOBS)
    summarise(JOBS)


if __name__ == "__main__":
    main()
