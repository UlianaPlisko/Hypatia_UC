"""UC01 Phase A tests. Run: pytest -q test_uc01.py   (from phase_a/, venv active)"""
import csv
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)  # uc01 folder: model, generator, schedulers (shared with phase B)
sys.path.insert(0, HERE)
sys.path.insert(0, SHARED)
import uc01_model as m  # noqa: E402
import schedulers as S  # noqa: E402
from evaluate import evaluate  # noqa: E402


def _run(script, *args):
    subprocess.run([sys.executable, os.path.join(SHARED, script), *args], check=True, cwd=HERE,
                   stdout=subprocess.DEVNULL)


@pytest.fixture(scope="module")
def dense(tmp_path_factory):
    """Small dense scenario (contention exists), 3 h, 60 stations."""
    d = tmp_path_factory.mktemp("uc01")
    gen, res = str(d / "gen"), str(d / "res")
    _run("gen_scenario.py", "--n-stations", "60", "--cluster", "45", "10", "3",
         "--duration-s", "10800", "--seed", "7", "--out", gen)
    _run("run_schedulers.py", "--scenario", gen, "--out", res)
    with open(os.path.join(gen, "params.json")) as f:
        params = json.load(f)
    prob = S.Problem.load(gen, params)
    summary = {s["scheduler"]: s for s in evaluate(gen, res)[0]}
    return {"gen": gen, "res": res, "params": params, "prob": prob, "summary": summary}


# ---------- physics ----------

def test_slant_range_zenith():
    assert abs(m.slant_range_m(90) - 600e3) < 1.0
    assert abs(m.slant_range_m(30) - 1075e3) < 2e3


def test_cost_monotonic_in_elevation():
    p = m.DEFAULT_PARAMS
    e = [float(m.slot_energy_j(m.slant_range_m(el), p)) for el in range(10, 91, 5)]
    assert all(a > b for a, b in zip(e, e[1:]))


def test_zenith_vs_10deg_about_10x():
    p = m.DEFAULT_PARAMS
    ratio = m.slot_energy_j(m.slant_range_m(10), p) / m.slot_energy_j(m.slant_range_m(90), p)
    assert 8 < ratio < 11


def test_baseline_link_budget():
    b = m.baseline_link_budget()
    assert abs(b["harvest_dbm"] - (-68)) < 1.5
    assert abs(b["gap_to_1uW_db"] - 38) < 1.5
    assert b["backscatter_dbm"] < -170   # far below any receiver -> infeasible


def test_unusable_slot_when_power_exceeds_max():
    p = dict(m.DEFAULT_PARAMS, p_tx_max_dbm=0.0)
    assert np.isinf(m.slot_energy_j(m.slant_range_m(10), p))


# ---------- geometry from Hypatia ----------

def test_visibility_respects_min_elevation(dense):
    with open(os.path.join(dense["gen"], "visibility.csv")) as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert min(float(r["elevation_deg"]) for r in rows) >= dense["params"]["min_elevation_deg"]
    assert max(float(r["distance_m"]) for r in rows) <= m.slant_range_m(10) * 1.02
    assert min(float(r["distance_m"]) for r in rows) >= 600e3 * 0.98


# ---------- schedulers ----------

@pytest.mark.parametrize("name", list(S.SCHEDULERS))
def test_no_slot_conflicts(dense, name):
    used = {}
    for ts in S.SCHEDULERS[name](dense["prob"]).values():
        for t in ts:
            used[t] = used.get(t, 0) + 1
    assert max(used.values()) <= dense["prob"].capacity


@pytest.mark.parametrize("name", list(S.SCHEDULERS))
def test_slots_are_visible_and_complete(dense, name):
    prob = dense["prob"]
    for i, ts in S.SCHEDULERS[name](prob).items():
        vis = {o[0] for o in prob.options[i]}
        assert set(ts) <= vis
        assert len(ts) == prob.stations[i]["slots_needed"]


@pytest.mark.parametrize("name", ["priority", "optimal"])
def test_energy_aware_never_overspend(dense, name):
    assert dense["summary"][name]["depleted"] == 0


def test_zenith_cheaper_than_asap(dense):
    s = dense["summary"]
    assert s["zenith"]["energy_per_delivered_j"] < s["asap"]["energy_per_delivered_j"]


def test_priority_protects_weak(dense):
    s = dense["summary"]
    assert s["priority"]["delivered"] >= s["asap"]["delivered"]
    assert s["priority"]["delivered"] >= s["zenith"]["delivered"]
    assert s["priority"]["p10_residual_frac"] >= s["asap"]["p10_residual_frac"]


def test_deterministic(tmp_path):
    for k in ("a", "b"):
        _run("gen_scenario.py", "--n-stations", "10", "--duration-s", "3600", "--seed", "3",
             "--out", str(tmp_path / k))
    for f in ("stations.csv", "visibility.csv"):
        assert (tmp_path / "a" / f).read_text() == (tmp_path / "b" / f).read_text()
