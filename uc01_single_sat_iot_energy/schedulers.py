"""
UC01 schedulers. Each takes a Problem and returns {station_id: [slot_index, ...]}.

Rules shared by all:
  - a slot (time step) serves at most K stations
  - a station only uses slots where it sees the satellite and the slot is not 'inf' cost
  - a station needs `slots_needed` slots to deliver its data (not necessarily consecutive)
Energy-aware schedulers (priority, optimal) never exceed a station's budget.
Naive ones (asap, zenith) transmit regardless; the evaluator marks them depleted.
"""
import csv
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

import uc01_model as m


class Problem:
    def __init__(self, stations, options, capacity=1):
        self.stations = stations          # id -> dict(slots_needed, budget, ...)
        self.options = options            # id -> list of (t_s, energy_j, elevation_deg), sorted by t
        self.capacity = capacity

    @classmethod
    def load(cls, scenario_dir, params, capacity=1):
        stations = {}
        with open(scenario_dir + "/stations.csv") as f:
            for r in csv.DictReader(f):
                stations[int(r["station_id"])] = {"slots_needed": int(r["slots_needed"]),
                                                  "budget": float(r["energy_budget_j"])}
        rows = defaultdict(list)
        with open(scenario_dir + "/visibility.csv") as f:
            for r in csv.DictReader(f):
                rows[int(r["station_id"])].append((float(r["t_s"]), float(r["distance_m"]),
                                                   float(r["elevation_deg"])))
        options = {}
        for i in stations:
            lst = rows.get(i, [])
            e = m.slot_energy_j(np.array([x[1] for x in lst]), params) if lst else []
            options[i] = [(t, float(ej), el) for (t, _, el), ej in zip(lst, e) if np.isfinite(ej)]
        return cls(stations, options, capacity)


def _first_seen(prob, i):
    return prob.options[i][0][0] if prob.options[i] else float("inf")


def _greedy(prob, order, key, budget_aware):
    used = defaultdict(int)
    out = {}
    for i in order:
        need = prob.stations[i]["slots_needed"]
        free = [o for o in prob.options[i] if used[o[0]] < prob.capacity]
        picked = sorted(free, key=key)[:need]
        if len(picked) < need:
            continue
        if budget_aware and sum(o[1] for o in picked) > prob.stations[i]["budget"]:
            continue  # cannot afford even its cheapest free slots: do not waste energy
        for o in picked:
            used[o[0]] += 1
        out[i] = [o[0] for o in picked]
    return out


def asap(prob):
    """S0: first come first served, transmit at the earliest free visible slots."""
    order = sorted(prob.stations, key=lambda i: _first_seen(prob, i))
    return _greedy(prob, order, key=lambda o: o[0], budget_aware=False)


def zenith(prob):
    """S1: in arrival order, each station grabs its own cheapest (highest elevation) free slots."""
    order = sorted(prob.stations, key=lambda i: _first_seen(prob, i))
    return _greedy(prob, order, key=lambda o: o[1], budget_aware=False)


def priority(prob):
    """S2 (proposed): poorest station first (lowest budget relative to its cheapest possible cost)
    takes its cheapest free slots; rich stations take what's left."""
    def tightness(i):
        opts = sorted(o[1] for o in prob.options[i])[:prob.stations[i]["slots_needed"]]
        return prob.stations[i]["budget"] / sum(opts) if opts else float("inf")
    order = sorted(prob.stations, key=tightness)
    return _greedy(prob, order, key=lambda o: o[1], budget_aware=True)


def optimal(prob, big=1e9):
    """S3: min-cost assignment of every needed slot, cost = energy / budget
    (fraction of the station's energy), via the Hungarian algorithm."""
    jobs, cols = [], {}
    for i, st in prob.stations.items():
        if not prob.options[i]:
            continue
        jobs += [i] * st["slots_needed"]
        for t, e, _ in prob.options[i]:
            cols.setdefault(t, None)
    times = sorted(cols)
    col_of = {}
    for t in times:
        col_of[t] = [len(col_of) * prob.capacity + c for c in range(prob.capacity)]
    n_cols = len(times) * prob.capacity
    cost = np.full((len(jobs), n_cols), big)
    for r, i in enumerate(jobs):
        b = prob.stations[i]["budget"]
        for t, e, _ in prob.options[i]:
            cost[r, col_of[t]] = e / b
    rows, cs = linear_sum_assignment(cost)
    t_of_col = {c: t for t, cl in col_of.items() for c in cl}
    got = defaultdict(list)
    for r, c in zip(rows, cs):
        if cost[r, c] < big:
            got[jobs[r]].append(t_of_col[c])
    out = {}
    for i, ts in got.items():
        if len(ts) < prob.stations[i]["slots_needed"]:
            continue
        e = {t: en for t, en, _ in prob.options[i]}
        if sum(e[t] for t in ts) <= prob.stations[i]["budget"]:
            out[i] = sorted(ts)
    return out


SCHEDULERS = {"asap": asap, "zenith": zenith, "priority": priority, "optimal": optimal}
