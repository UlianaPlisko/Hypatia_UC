# UC01: Feasibility on Hypatia, required changes, how to run

## 1. Short answer

**Yes, it can run, but in two phases.** Hypatia does not have an energy model or uplink
scheduling. It does have everything needed for the geometry: satellite orbits, ground
stations, time-varying distances and visibility.

| Phase | Where it runs | Changes to Hypatia | What it gives us |
|-------|---------------|--------------------|------------------|
| **A. Analytical / scheduling** (recommended first) | `satgenpy` (Python) only | None to the core. New scripts in `use_cases/` only | Visibility windows, distance/elevation per time step, energy cost per slot, scheduler comparison |
| **B. Packet-level** (optional, later) | `ns3-sat-sim` (ns-3.31) | Yes, C++ changes (see §4) | Real packets, queues, collisions/contention, energy drain via the ns-3 `energy` module |

Phase A answers the research question (which schedule saves energy and protects
low-energy stations). Phase B checks that the schedule still holds up with real traffic.

## 2. What Hypatia already provides (and we reuse)

| Need | Existing Hypatia piece |
|------|-------------------------|
| A single satellite | `satgenpy/satgen/tles/generate_tles_from_scratch.py`, use `num_orbits=1, num_sats_per_orbit=1` |
| Many ground stations | Custom `ground_stations.basic.txt` (`id,name,lat,lon,elev`) → `satgen.extend_ground_stations(...)` |
| No ISLs (single sat) | `satgen.generate_empty_isls(...)` |
| GS↔sat distance at time t | `satgen.distance_tools.distance_m_ground_station_to_satellite(gs, sat, epoch, date)` |
| Visibility (in range) | `max_gsl_length_m` in `generate_dynamic_state.py:202`; derived from min elevation like `paper/satellite_networks_state/main_kuiper_630.py` |
| Visualization | `satviz/` (Cesium) for the orbit and ground stations |
| Packet sim engine | `ns3-sat-sim` with `GSLNetDevice` / `GSLChannel` (distance-based delay) |
| Energy framework (Phase B) | ns-3 `src/energy` (`BasicEnergySource`, `DeviceEnergyModel`). It's present in the tree |

## 3. What is missing / must be added (Phase A, Python only)

1. **Scenario generator** `gen_scenario.py` (shared, uc01 root)
   - 1 satellite at 600 km (mean motion ≈ 14.9 rev/day), inclination chosen so that
     the stations are covered (e.g. 53° or a polar orbit at 97.8°)
   - N stations (e.g. 50–200) placed randomly or on a lat/lon grid under the ground track
   - Random initial energy per station `E0_i ~ U(Emin, Emax)` with a **fixed seed**
2. **Geometry extractor**: for every time step Δt (e.g. 1 s) and every station, compute
   distance `d_i(t)` and elevation `ε_i(t)`, keeping only `ε ≥ ε_min` (e.g. 10°).
   We need elevation, which Hypatia does not output directly. It is simple to compute
   from ECEF vectors (`geodetic2cartesian` already exists in `distance_tools.py`).
3. **Energy model module** `energy_model.py` (see `02_test_design_and_analysis.md` §3)
4. **Schedulers** `schedulers.py`: ASAP, zenith-greedy, energy-aware priority, optimal (min-cost assignment)
5. **Evaluation + plots** `phase_a/evaluate.py` → CSV + figures in `phase_a/results*/`
6. **Unit tests** `phase_a/test_uc01.py` (pytest, same style as `satgenpy/tests/`)

None of these touch `satgenpy/satgen/*`. They only import from it.

## 4. What must change in ns-3 (Phase B, only if we go packet-level)

| Change | File(s) | Why |
|--------|---------|-----|
| Allow the **satellite as an endpoint** (traffic sink) | `contrib/satellite-network/model/topology-satellite-network.cc:60` (`// Only ground stations are valid endpoints`) | Today only GS↔GS flows exist. IoT data terminates at the satellite |
| Install a `UdpSink`/`PacketSink` on the satellite node | `scratch/main_satnet/main_satnet.cc` | Receive IoT packets |
| **Schedule-driven sender app**: sends station i's payload only in its assigned slot | new app in `contrib/basic-sim/model/apps/` (based on `udp-burst-application`) reading `schedule.csv` | Apply the Python schedule |
| **Energy accounting**: `BasicEnergySource` per GS + a custom `GslTxEnergyModel` whose Tx power depends on distance | new files + hook in `gsl-net-device.cc` `Send()` | Drain energy per transmitted bit |
| Single-sat forwarding state | use `algorithm_free_one_only_gs_relays` with `isls_none`, or a trivial fstate (GS → sat directly) | No routing needed, 1 hop |
| (Optional) Rate dependent on SNR | `gsl-channel.cc` | Hypatia uses a fixed GSL data rate. Fine for a first version |

Effort estimate: Phase A about 1–2 days. Phase B about 1–2 weeks (C++ + ns-3 build).

## 5. How to run (Phase A, implemented, see `phase_a/results.md`)

`satgenpy` has no `setup.py`, so it can't be pip-installed. `uc01_model.py` adds it to
`sys.path` automatically. The only extra packages are pytest, matplotlib and scipy.

```bash
cd ~/hypatia
source hypatia-venv/bin/activate
pip install pytest matplotlib scipy       # once

# everything (both scenarios + tests), about 30 s:
bash use_cases/uc01_single_sat_iot_energy/phase_a/run_all.sh

# or step by step (from phase_a/; shared scripts are one level up):
cd use_cases/uc01_single_sat_iot_energy/phase_a
python ../gen_scenario.py   --n-stations 100 --seed 42 --duration-s 86400 --step-s 1 --out gen/
python ../gen_scenario.py   --n-stations 200 --cluster 45 10 3 --duration-s 21600 --out gen_dense/   # dense case
python ../run_schedulers.py --scenario gen/ --schedulers asap,zenith,priority,optimal --capacity 1 --out results/
python evaluate.py          --scenario gen/ --results results/     # → summary.csv, per_station.csv, fig_*.png
pytest -q test_uc01.py
```

`phase_a/gen*/` (raw geometry, about 5 MB each) is git-ignored and can be regenerated. `phase_a/results*/` is kept.

Duration: one LEO orbit is about 96 min. A station sees a 600 km satellite only a few
times per day for about 5–10 min per pass, so simulate **≥ 24 h** so every station gets
at least one pass (or pick the orbit and stations so the passes are guaranteed).

## 6. How to run (Phase B, after the C++ changes)

```bash
cd ~/hypatia/ns3-sat-sim && bash build.sh --optimized     # build.sh already has --disable-werror locally
cd ~/hypatia/paper/ns3_experiments/...                    # or a new run dir under use_cases/uc01_.../ns3_run
# config_ns3.properties: satellite_network_dir=../gen/, schedule file, energy params
cd ~/hypatia/ns3-sat-sim/simulator
./waf --run="main_satnet --run_dir='<run_dir>'"
```

## 7. Risks / limits to keep in mind

- **The baseline link budget says direct LEO powering of passive A-IoT tags is not feasible**
  (harvest ≈ −68 dBm at zenith, 38 dB short of 1 µW. Backscatter ≈ −182 dBm at the satellite).
  So in UC01 the stations are treated as **active** transmitters with their own battery/harvested
  energy, and the passive-tag issue is documented as an open point (relay/reader topology →
  future use case).
- Hypatia ignores atmosphere, rain, antenna patterns and Doppler. The energy model only covers free-space path loss.
- With only 1 satellite, stations with no pass in the time horizon cannot send at all. Report this separately, not as a scheduler failure.
