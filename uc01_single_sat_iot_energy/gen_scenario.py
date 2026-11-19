"""
UC01 step 1: generate the scenario with Hypatia's satgenpy.

Outputs (in --out):
  tles.txt                    1 satellite (Hypatia format, satgen.generate_tles_from_scratch_with_sgp)
  ground_stations.basic.txt   N random stations (Hypatia format id,name,lat,lon,elev)
  stations.csv                station_id,lat,lon,bits,slots_needed,energy_budget_j
  visibility.csv              t_s,station_id,distance_m,elevation_deg  (only elevation >= min)
  params.json                 parameters used
"""
import argparse
import csv
import json
import math
import os

import numpy as np

import uc01_model as m
import satgen
import ephem

EPOCH = "2000-01-01 00:00:00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-stations", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--duration-s", type=int, default=86400)
    ap.add_argument("--step-s", type=float, default=1.0)
    ap.add_argument("--inclination-deg", type=float, default=53.0)
    ap.add_argument("--max-abs-lat", type=float, default=50.0)
    ap.add_argument("--cluster", type=float, nargs=3, metavar=("LAT", "LON", "HALF_WIDTH_DEG"),
                    help="place all stations in a lat/lon box (dense case, causes slot contention)")
    ap.add_argument("--min-elevation-deg", type=float, default=10.0)
    ap.add_argument("--bits-min", type=int, default=1000)
    ap.add_argument("--bits-max", type=int, default=10000)
    ap.add_argument("--energy-lo", type=float, default=0.1,
                    help="budget = U(lo,hi) x energy needed at min elevation")
    ap.add_argument("--energy-hi", type=float, default=1.0)
    ap.add_argument("--out", default="gen")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    p = dict(m.DEFAULT_PARAMS)
    p["min_elevation_deg"] = a.min_elevation_deg
    p["slot_s"] = a.step_s
    rng = np.random.default_rng(a.seed)

    # --- 1 satellite at 600 km (Hypatia TLE generator) ---
    mu = 3.986004418e14
    r = 6378135.0 + p["altitude_m"]
    mean_motion = 86400.0 / (2 * math.pi * math.sqrt(r ** 3 / mu))
    tles_path = os.path.join(a.out, "tles.txt")
    satgen.generate_tles_from_scratch_with_sgp(
        tles_path, "UC01", 1, 1, False, a.inclination_deg, 0.0000001, 0.0, mean_motion)
    sat = satgen.read_tles(tles_path)["satellites"][0]

    # --- N random ground stations (uniform on the sphere within +-max_abs_lat) ---
    s = math.sin(math.radians(a.max_abs_lat))
    lat = np.degrees(np.arcsin(rng.uniform(-s, s, a.n_stations)))
    lon = rng.uniform(-180, 180, a.n_stations)
    if a.cluster:
        c_lat, c_lon, hw = a.cluster
        lat = rng.uniform(c_lat - hw, c_lat + hw, a.n_stations)
        lon = rng.uniform(c_lon - hw, c_lon + hw, a.n_stations)
    with open(os.path.join(a.out, "ground_stations.basic.txt"), "w") as f:
        for i in range(a.n_stations):
            f.write("%d,Station-%d,%.6f,%.6f,0\n" % (i, i, lat[i], lon[i]))

    gs_ecef = m.geodetic_to_ecef(lat, lon, 0.0)
    gs_up = m.up_vectors(lat, lon)

    # --- Geometry per time step: one ephem call per step, then numpy for all stations ---
    n_steps = int(a.duration_s / a.step_s)
    t0 = ephem.Date(EPOCH)
    rows = []
    for k in range(n_steps):
        t = k * a.step_s
        sat.compute(ephem.Date(t0 + t / 86400.0), epoch=EPOCH)
        s_ecef = m.geodetic_to_ecef(math.degrees(sat.sublat), math.degrees(sat.sublong), sat.elevation)
        v = s_ecef - gs_ecef
        d = np.linalg.norm(v, axis=1)
        elev = np.degrees(np.arcsin(np.einsum("ij,ij->i", v, gs_up) / d))
        for i in np.nonzero(elev >= a.min_elevation_deg)[0]:
            rows.append((t, int(i), float(d[i]), float(elev[i])))

    with open(os.path.join(a.out, "visibility.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "station_id", "distance_m", "elevation_deg"])
        for t, i, d, e in rows:
            w.writerow([t, i, "%.1f" % d, "%.3f" % e])

    # --- Data volume and energy budget per station ---
    worst_slot_j = float(m.slot_energy_j(m.slant_range_m(a.min_elevation_deg, p["altitude_m"]), p))
    bits = rng.integers(a.bits_min, a.bits_max + 1, a.n_stations)
    slots_needed = np.ceil(bits / (p["rate_bps"] * p["slot_s"])).astype(int)
    budget = rng.uniform(a.energy_lo, a.energy_hi, a.n_stations) * slots_needed * worst_slot_j
    with open(os.path.join(a.out, "stations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "lat", "lon", "bits", "slots_needed", "energy_budget_j"])
        for i in range(a.n_stations):
            w.writerow([i, "%.6f" % lat[i], "%.6f" % lon[i], bits[i], slots_needed[i], "%.6e" % budget[i]])

    with open(os.path.join(a.out, "params.json"), "w") as f:
        json.dump({**p, **vars(a), "mean_motion_rev_per_day": mean_motion,
                   "worst_slot_energy_j": worst_slot_j}, f, indent=2)

    seen = len({i for _, i, _, _ in rows})
    print("Satellite: 600 km, %.2f rev/day, incl %.1f deg" % (mean_motion, a.inclination_deg))
    print("Stations: %d, with at least one pass: %d" % (a.n_stations, seen))
    print("Visible (station, step) samples: %d -> %s" % (len(rows), a.out))


if __name__ == "__main__":
    main()
