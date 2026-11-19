# UC01: Single LEO satellite, many IoT ground stations, energy-aware uplink scheduling

## 1. Scenario

- Earth with **N terrestrial IoT stations** (e.g. N = 100) at fixed lat/lon.
- **One LEO satellite** at h = 600 km, f = 2 GHz, passing over them.
- Each station i has a finite energy budget **E0_i** (random, fixed seed) and must upload
  **B_i bits** of IoT data to the satellite at least once in the time horizon T.
- The satellite can receive from **one station at a time** (or K at a time, in TDMA slots
  of length τ, e.g. 1 s).

**Goal:** choose *when* each station transmits so that
1. every station that can see the satellite delivers its data,
2. total energy spent is as low as possible, and
3. **low-energy stations are protected**: they get the cheapest slots (near zenith),
   while stations with plenty of energy accept more expensive slots (lower elevation, earlier/later in the pass).

## 2. Why zenith is cheapest (geometry)

Slant range at elevation ε (R = 6371 km, h = 600 km):

d(ε) = √((R+h)² − (R cos ε)²) − R sin ε

| Elevation ε | Distance d | Energy factor (d/h)² | Extra loss vs zenith |
|-------------|-----------:|---------------------:|---------------------:|
| 90° (zenith) | 600 km | 1.00× | 0.0 dB |
| 60° | 683 km | 1.30× | 1.1 dB |
| 45° | 815 km | 1.84× | 2.7 dB |
| 30° | 1075 km | 3.21× | 5.1 dB |
| 20° | 1392 km | 5.38× | 7.3 dB |
| 10° | 1932 km | 10.36× | 10.2 dB |

So sending at 10° costs about **10× the energy** of sending at zenith. That gap is what the scheduler works with.
Note: not every pass goes through zenith. A station off the ground track sees a maximum
elevation ε_max,i < 90°, so its cheapest slot is at its own ε_max.

## 3. Energy model

### 3.1 Baseline check (from the book's first model)
Satellite: 200 W (53 dBm), 36 dBi, 2 GHz, 600 km, assumed tag values:
- Harvested power at the tag at zenith ≈ **−68 dBm**, about **38 dB below 1 µW (−30 dBm)** peak.
- Backscatter return at the satellite ≈ **−182 dBm**.
- ⇒ **Direct LEO powering of passive A-IoT tags looks infeasible.** We need a reader or relay topology.
  These numbers depend on the assumed tag gain, efficiency and reflection factor.

**Consequence for UC01:** stations are modelled as **active, battery-powered transmitters**.
The same free-space model still applies, used in the uplink direction.

### 3.2 Uplink energy per slot (Friis / free-space)
FSPL(d) = (4π d f / c)². At 600 km, 2 GHz this is ≈ 154 dB.

Required Tx power to close the link with receiver sensitivity P_rx,min:

P_tx,i(t) = P_rx,min · FSPL(d_i(t)) / (G_tx · G_rx)

Energy to send B_i bits at rate r: **E_i(t) = (P_tx,i(t)/η_PA + P_circuit) · B_i / r**

- η_PA: power-amplifier efficiency (e.g. 0.3)
- P_circuit: fixed electronics power (e.g. 10 mW)
- If P_tx,i(t) > P_tx,max, slot t is **not usable** for station i.

Normalised form used by the schedulers (simple, parameter-free):
**cost_i(t) = (d_i(t) / h)²**. Absolute joules come from the full formula.

### 3.3 Starting parameters (all configurable)

| Param | Value |
|-------|-------|
| f | 2 GHz |
| h | 600 km |
| G_rx (sat) | 36 dBi |
| G_tx (station) | 0–3 dBi |
| P_rx,min | −120 dBm (narrowband LPWAN-like) |
| P_tx,max | 23 dBm (200 mW) |
| r | 1 kbps |
| B_i | 1–10 kbit |
| ε_min | 10° |
| E0_i | U(0.1, 1) × E_ref, seed 42 |
| Δt / slot τ | 1 s |
| T | 24 h |

## 4. Schedulers to compare

| # | Name | Rule | Role |
|---|------|------|------|
| S0 | **ASAP** | Transmit at first visibility (first come, first served) | Naive baseline: worst energy |
| S1 | **Zenith-greedy** | Each station picks its own min-cost slot; conflicts go to whoever asked first | Selfish optimum, shows contention |
| S2 | **Energy-aware priority** (proposed) | Sort stations by *remaining energy ascending* (or by E0_i / cost_min,i). The lowest-energy station takes its cheapest free slot, then the next, and so on. Rich stations end up with the slots off-peak | The idea we are proposing |
| S3 | **Weighted optimal** | Min-cost assignment: minimise Σ w_i · cost_i(t) with w_i = 1/E_i (Hungarian / `scipy.optimize.linear_sum_assignment`) | Upper bound / reference |
| S4 | (opt.) **Max-min residual** | Maximise min_i (E_i − E_i,spent) (LP/ILP) | Fairness-optimal reference |

Constraints for all of them: one station per slot (or K), slot must be within visibility,
P_tx ≤ P_tx,max, E_spent,i ≤ E_i.

## 5. What we measure

| Metric | Meaning |
|--------|---------|
| **Delivery ratio** | stations that delivered / stations that had a pass |
| **Total energy** Σ E_spent | overall efficiency |
| **Min residual energy** min_i(E_i − E_spent,i) | protection of the weakest station (key metric) |
| **# depleted stations** | stations whose energy ran out / could not afford any slot |
| **Mean elevation at Tx** | sanity check: weak stations should be near ε_max |
| **Jain fairness index** on residual energy | fairness |
| **Latency** (Tx time − first visibility) | the price paid by rich stations for waiting |

## 6. Tests (pytest)

| Test | Checks |
|------|--------|
| `test_slant_range_zenith` | d(90°) = h ± 1 m. d(30°) ≈ 1075 km |
| `test_cost_monotonic` | cost decreases as elevation increases |
| `test_baseline_link_budget` | reproduces ≈ −68 dBm harvest and the ≈ 38 dB gap (regression of §3.1) |
| `test_visibility_single_sat` | with Hypatia geometry, a station under the ground track has ε_max ≈ 90° |
| `test_no_slot_conflicts` | no slot assigned to more than K stations, for every scheduler |
| `test_energy_never_negative` | E_spent,i ≤ E_i for all i |
| `test_priority_protects_weak` | S2 min-residual ≥ S0 and S1 min-residual |
| `test_priority_near_optimal` | S2 total weighted cost within X % of S3 |
| `test_zenith_beats_asap` | S1 total energy < S0 total energy |
| `test_deterministic` | same seed → identical schedule |

## 7. Expected results (hypotheses)

1. ASAP spends the most energy (transmits around ε_min, up to about 10× zenith cost).
2. Zenith-greedy minimises energy when stations are sparse, but with dense stations under one pass
   it causes contention, and the losers fall back to costly slots. That can hit weak stations hardest.
3. Energy-aware priority gives a slightly higher (or equal) total energy than S3, but a clearly
   **higher minimum residual energy** and fewer depleted stations.
4. Rich stations get higher latency and lower elevation. This trade-off is intended.

## 8. Experiment sweeps

- N ∈ {10, 50, 100, 200}: density vs contention
- Slot capacity K ∈ {1, 2, 4}
- Energy spread: E0 ~ U(0.1,1), U(0.5,1), bimodal
- ε_min ∈ {10°, 20°, 30°}
- Station layout: on the ground track vs spread over the coverage band

## 9. Outputs

```
use_cases/uc01_single_sat_iot_energy/
├── README.md
├── 01_feasibility_and_setup.md
├── 02_test_design_and_analysis.md
├── uc01_model.py, gen_scenario.py,      # shared by phase A and B
│   schedulers.py, run_schedulers.py
├── phase_a/                             # analytical (Python + satgenpy)
│   ├── evaluate.py, test_uc01.py, run_all.sh
│   ├── results.md
│   ├── gen*/                            # generated geometry (git-ignored)
│   └── results*/                        # schedule_<sched>.csv, summary.csv, figures
└── phase_b/                             # ns-3 packet level (planned)
    └── README.md
```

Figures: elevation vs time per pass with Tx markers, residual energy CDF per scheduler,
total-energy and min-residual bar charts.

## 10. Open points / next use cases

- Passive A-IoT is infeasible directly from LEO (§3.1). Study a relay/reader (drone, ground reader,
  HAPS) topology as UC02.
- Multiple satellites (Hypatia constellations like Kuiper/Starlink): more passes, less contention.
- Energy harvesting over time (solar), so E_i(t) grows between passes.
- Phase B ns-3 validation with real packets.
