# UC01: Single LEO satellite, many IoT ground stations, energy-aware uplink scheduling

One satellite at 600 km passes over many IoT stations. Each station has a limited energy budget
and must upload its data. Sending near zenith is cheapest (about 10× cheaper than at 10° elevation).
The proposed scheduler gives the cheap slots to the stations with the least energy first.

## Documents

| File | Content |
|------|---------|
| [01_feasibility_and_setup.md](01_feasibility_and_setup.md) | Can it run on Hypatia, what to change (phase A and B), how to run |
| [02_test_design_and_analysis.md](02_test_design_and_analysis.md) | Scenario, energy model, schedulers, metrics, tests, hypotheses |
| [phase_a/results.md](phase_a/results.md) | Phase A results and analysis |
| [phase_b/README.md](phase_b/README.md) | Phase B (ns-3) plan |

## Layout

```
uc01_single_sat_iot_energy/
├── uc01_model.py        shared: parameters + energy model
├── gen_scenario.py      shared: satellite, stations, geometry (Hypatia satgenpy)
├── schedulers.py        shared: S0 ASAP, S1 zenith, S2 priority, S3 optimal
├── run_schedulers.py    shared: writes schedule_<name>.csv (Phase B input)
├── phase_a/             analytical simulation: evaluate.py, test_uc01.py, run_all.sh, results
└── phase_b/             ns-3 packet-level simulation (planned)
```

Shared code stays in the root because Phase B needs the same scenario, energy model and schedules.

## Quick start (Phase A)

```bash
cd ~/hypatia && source hypatia-venv/bin/activate
pip install pytest matplotlib scipy      # once
bash use_cases/uc01_single_sat_iot_energy/phase_a/run_all.sh
```

| Phase | Status |
|-------|--------|
| A: analytical (Python) | Done, 19 tests pass |
| B: packet level (ns-3) | Planned |
