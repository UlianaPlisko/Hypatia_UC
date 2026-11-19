"""
UC01 step 2: run the schedulers on a generated scenario.

Writes results/schedule_<name>.csv with one row per transmitted slot:
  scheduler,station_id,t_s,energy_j,elevation_deg
"""
import argparse
import csv
import json
import os
import time

import schedulers as S
from schedulers import Problem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="gen")
    ap.add_argument("--schedulers", default="asap,zenith,priority,optimal")
    ap.add_argument("--capacity", type=int, default=1, help="stations served per slot (K)")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.scenario, "params.json")) as f:
        params = json.load(f)
    prob = Problem.load(a.scenario, params, a.capacity)

    for name in a.schedulers.split(","):
        t0 = time.time()
        sched = S.SCHEDULERS[name](prob)
        with open(os.path.join(a.out, "schedule_%s.csv" % name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scheduler", "station_id", "t_s", "energy_j", "elevation_deg"])
            for i, ts in sorted(sched.items()):
                info = {t: (e, el) for t, e, el in prob.options[i]}
                for t in ts:
                    w.writerow([name, i, t, "%.6e" % info[t][0], "%.3f" % info[t][1]])
        print("%-9s scheduled %3d stations in %.1fs" % (name, len(sched), time.time() - t0))
    with open(os.path.join(a.out, "run.json"), "w") as f:
        json.dump(vars(a), f, indent=2)


if __name__ == "__main__":
    main()
