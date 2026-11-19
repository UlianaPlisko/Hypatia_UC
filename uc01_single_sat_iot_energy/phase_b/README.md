# UC01 Phase B: packet-level simulation in ns-3 (planned)

Not implemented yet. The goal is to check that the Phase A schedules still hold with real packets.

## Inputs (reused from the uc01 root)

- `../gen_scenario.py` → `tles.txt`, `ground_stations.basic.txt` (Hypatia formats)
- `../run_schedulers.py` → `schedule_<name>.csv` (which station transmits in which second)
- `../uc01_model.py` → energy parameters (P_rx,min, margin, PA efficiency, P_circuit)

## Changes needed in `ns3-sat-sim` (see `../01_feasibility_and_setup.md` §4)

1. Allow the satellite as a traffic endpoint (`topology-satellite-network.cc:60`).
2. Packet sink on the satellite node (`scratch/main_satnet/main_satnet.cc`).
3. Schedule-driven sender app reading `schedule_<name>.csv` (based on `udp-burst-application`).
4. Energy: ns-3 `BasicEnergySource` per station + a distance-dependent `GslTxEnergyModel` hooked into `GSLNetDevice::Send()`.
5. 1-hop forwarding state (`isls_none`, station → satellite).

## Planned layout

```
phase_b/
├── README.md
├── gen_ns3_inputs.py     scenario + schedule → ns-3 run dir (config_ns3.properties, ...)
├── ns3_patches/          C++ changes, or a note pointing to the ns3-sat-sim commits
├── run_ns3.sh
├── compare_with_phase_a.py
└── results.md
```

## How it will run

```bash
cd ~/hypatia/ns3-sat-sim && bash build.sh --optimized
cd ~/hypatia/ns3-sat-sim/simulator
./waf --run="main_satnet --run_dir='<phase_b run dir>'"
```
