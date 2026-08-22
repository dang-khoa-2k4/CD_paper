"""Generate the geometry-level model-size/solve-time correlation figure."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / "figures" / "correlation_geometry_level.pdf"
METRICS = ("num_regions", "num_edges", "t_solve")


def load_geometry_level_data() -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in sorted(ROOT.glob("*_summary.csv"))]
    raw = pd.concat(frames, ignore_index=True)
    selected = raw.loc[raw["metric"].isin(METRICS)]
    wide = (
        selected.pivot_table(
            index=["map_type", "seed", "decomp_method"],
            columns="metric",
            values="median",
            aggfunc="first",
        )
        .reset_index()
        .dropna(subset=list(METRICS))
    )
    if len(wide) != 100:
        raise RuntimeError(f"Expected 100 method--geometry records, found {len(wide)}")
    return wide


def main() -> None:
    data = load_geometry_level_data()
    colors = {"acd": "#2878B5", "vcc": "#D95319"}
    labels = {"acd": "ACD", "vcc": "VCC"}
    panels = (("num_regions", r"Number of regions $N_R$"),
              ("num_edges", r"Number of edges $N_E$"))

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "legend.fontsize": 8,
    })
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.75), sharey=True)

    for ax, (metric, xlabel) in zip(axes, panels):
        for method in ("acd", "vcc"):
            subset = data.loc[data["decomp_method"] == method]
            ax.scatter(
                subset[metric], subset["t_solve"], s=24,
                color=colors[method], alpha=0.72, edgecolor="white",
                linewidth=0.35, label=labels[method], rasterized=True,
            )
        rho, p_value = spearmanr(data[metric], data["t_solve"])
        ax.text(
            0.04, 0.95,
            rf"Spearman $\rho={rho:.3f}$" + "\n" + rf"$p={p_value:.1e}$",
            transform=ax.transAxes, ha="left", va="top",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white",
                  "edgecolor": "0.75", "alpha": 0.9},
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.grid(True, which="major", color="0.86", linewidth=0.6)
        ax.grid(True, which="minor", color="0.93", linewidth=0.4)

    axes[0].set_ylabel(r"Geometry-level median solve time $t_{\rm solve}$ (s)")
    axes[1].legend(loc="lower right", frameon=True)
    fig.tight_layout(w_pad=1.2)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight", dpi=300)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
