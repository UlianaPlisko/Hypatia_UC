#!/bin/bash
# UC01 Phase A: full pipeline. Run from anywhere: bash use_cases/uc01_single_sat_iot_energy/phase_a/run_all.sh
# Shared code (model, generator, schedulers) lives one level up; outputs go into phase_a/.
set -e
cd "$(dirname "$0")"
source ../../../hypatia-venv/bin/activate
U=..

# Scenario 1: sparse - 100 random stations worldwide, 24 h
python $U/gen_scenario.py   --n-stations 100 --seed 42 --duration-s 86400 --step-s 1 --out gen/
python $U/run_schedulers.py --scenario gen/ --out results/
python evaluate.py          --scenario gen/ --results results/

# Scenario 2: dense - 200 stations in a 6x6 deg box around (45N, 10E), 6 h (slot contention)
python $U/gen_scenario.py   --n-stations 200 --seed 42 --cluster 45 10 3 --duration-s 21600 --out gen_dense/
python $U/run_schedulers.py --scenario gen_dense/ --out results_dense/
python evaluate.py          --scenario gen_dense/ --results results_dense/

pytest -q test_uc01.py
