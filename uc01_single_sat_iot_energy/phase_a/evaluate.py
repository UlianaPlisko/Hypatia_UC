"""
UC01 step 3: compute metrics per scheduler and draw figures.

  results/summary.csv     one row per scheduler
  results/per_station.csv one row per (scheduler, station)
  results/*.png           figures
"""
import argparse
import csv
import json
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ORDER = ["asap", "zenith", "priority", "optimal"]
COLORS = {"asap": "#2a78d6", "zenith": "#eb6834", "priority": "#1baf7a", "optimal": "#6250d6"}
LABELS = {"asap": "S0 ASAP", "zenith": "S1 Zenith-greedy", "priority": "S2 Energy priority",
          "optimal": "S3 Weighted optimal"}


def jain(x):
    x = np.asarray(x, float)
    return float(x.sum() ** 2 / (len(x) * (x ** 2).sum())) if len(x) and (x ** 2).sum() > 0 else 0.0


def evaluate(scenario, results):
    st = {}
    with open(os.path.join(scenario, "stations.csv")) as f:
        for r in csv.DictReader(f):
            st[int(r["station_id"])] = float(r["energy_budget_j"])
    first_seen, max_elev = {}, defaultdict(float)
    with open(os.path.join(scenario, "visibility.csv")) as f:
        for r in csv.DictReader(f):
            i = int(r["station_id"])
            first_seen.setdefault(i, float(r["t_s"]))
            max_elev[i] = max(max_elev[i], float(r["elevation_deg"]))
    reachable = set(first_seen)

    summary, per_station = [], []
    for name in ORDER:
        path = os.path.join(results, "schedule_%s.csv" % name)
        if not os.path.exists(path):
            continue
        spent, elev, last_t = defaultdict(float), defaultdict(list), {}
        with open(path) as f:
            for r in csv.DictReader(f):
                i = int(r["station_id"])
                spent[i] += float(r["energy_j"])
                elev[i].append(float(r["elevation_deg"]))
                last_t[i] = max(last_t.get(i, 0), float(r["t_s"]))
        residual = []
        delivered = depleted = 0
        lat = []
        for i in sorted(reachable):
            b = st[i]
            s = spent.get(i, 0.0)
            ok = i in spent and s <= b
            dep = i in spent and s > b      # transmitted but ran out of energy => data lost
            delivered += ok
            depleted += dep
            res = max(b - s, 0.0) / b
            residual.append(res)
            if ok:
                lat.append(last_t[i] - first_seen[i])
            per_station.append({"scheduler": name, "station_id": i, "budget_j": b, "spent_j": s,
                                "residual_frac": res, "delivered": int(ok), "depleted": int(dep),
                                "mean_tx_elev_deg": np.mean(elev[i]) if elev[i] else "",
                                "max_elev_deg": max_elev[i]})
        summary.append({
            "scheduler": name,
            "reachable_stations": len(reachable),
            "delivered": delivered,
            "delivery_ratio": delivered / len(reachable),
            "depleted": depleted,
            "total_energy_j": sum(spent.values()),
            "energy_per_delivered_j": sum(spent.values()) / max(delivered, 1),
            "min_residual_frac": min(residual),
            "p10_residual_frac": float(np.percentile(residual, 10)),
            "jain_residual": jain(residual),
            "mean_tx_elev_deg": float(np.mean([e for v in elev.values() for e in v])) if elev else 0,
            "mean_latency_s": float(np.mean(lat)) if lat else 0,
        })
    return summary, per_station


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def plots(summary, per_station, out):
    names = [s["scheduler"] for s in summary]
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True, "grid.color": "#e5e4e0", "grid.linewidth": 0.6})

    # 1. bar charts: delivery, depleted, total energy, min residual (one chart per measure)
    fig, axs = plt.subplots(1, 4, figsize=(16, 3.8))
    for ax, (k, title) in zip(axs, [("delivery_ratio", "Delivery ratio"),
                                    ("depleted", "Depleted stations"),
                                    ("energy_per_delivered_j", "Energy per delivered station (J)"),
                                    ("p10_residual_frac", "10th pct residual energy (frac.)")]):
        vals = [s[k] for s in summary]
        bars = ax.bar([LABELS[n].split()[0] for n in names], vals,
                      color=[COLORS[n] for n in names], width=0.6, edgecolor="white", linewidth=2)
        ax.bar_label(bars, fmt="%.3g", fontsize=8, color="#52514e")
        ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_summary_bars.png"), dpi=130)
    plt.close(fig)

    # 2. CDF of residual energy fraction
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for n in names:
        r = np.sort([p["residual_frac"] for p in per_station if p["scheduler"] == n])
        ax.step(r, np.arange(1, len(r) + 1) / len(r), where="post", lw=2, color=COLORS[n], label=LABELS[n])
    ax.set_xlabel("Residual energy / initial budget")
    ax.set_ylabel("CDF of stations")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_residual_cdf.png"), dpi=130)
    plt.close(fig)

    # 3. budget vs mean Tx elevation: do poor stations get the high-elevation slots?
    fig, axs = plt.subplots(1, len(names), figsize=(4 * len(names), 3.6), sharey=True)
    for ax, n in zip(np.atleast_1d(axs), names):
        pts = [p for p in per_station if p["scheduler"] == n and p["mean_tx_elev_deg"] != ""]
        ax.scatter([p["budget_j"] for p in pts], [p["mean_tx_elev_deg"] for p in pts], s=14,
                   color=COLORS[n], edgecolors="white", linewidths=0.8)
        ax.set_title(LABELS[n], fontsize=10)
        ax.set_xlabel("Energy budget (J)")
    np.atleast_1d(axs)[0].set_ylabel("Mean elevation at Tx (deg)")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_budget_vs_elevation.png"), dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="gen")
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    summary, per_station = evaluate(a.scenario, a.results)
    write_csv(os.path.join(a.results, "summary.csv"), summary)
    write_csv(os.path.join(a.results, "per_station.csv"), per_station)
    plots(summary, per_station, a.results)
    keys = ["delivered", "depleted", "total_energy_j", "energy_per_delivered_j",
            "min_residual_frac", "p10_residual_frac", "jain_residual", "mean_tx_elev_deg", "mean_latency_s"]
    print("%-9s " % "" + " ".join("%14s" % k[:14] for k in keys))
    for s in summary:
        print("%-9s " % s["scheduler"] + " ".join("%14.4g" % s[k] for k in keys))


if __name__ == "__main__":
    main()
