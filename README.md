# Use cases

Each use case has its own folder with:

- `README.md`: overview of the use case and its folder layout
- `01_feasibility_and_setup.md`: can it run on Hypatia, what has to change, how to run it
- `02_test_design_and_analysis.md`: what the test does, the models, what we want to show, metrics, expected results
- `phase_a/`: analytical simulation (Python + satgenpy) with code, tests and `results.md`
- `phase_b/`: packet-level simulation (ns-3), planned
- shared code (model, generator, schedulers) stays in the use-case root because both phases use it

| ID | Folder | Topic | Status |
|----|--------|-------|--------|
| UC01 | [uc01_single_sat_iot_energy](uc01_single_sat_iot_energy/) | 1 LEO satellite, many ground IoT stations, energy-aware uplink scheduling | A: done ([results](uc01_single_sat_iot_energy/phase_a/results.md)). B: planned |
