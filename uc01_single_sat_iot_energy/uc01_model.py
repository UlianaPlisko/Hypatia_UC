"""
UC01 shared model: parameters, geometry helpers and the uplink energy model.

All schedulers and tests import from here so the physics lives in one place.
"""
import math
import os
import sys

import numpy as np

# Make Hypatia's satgenpy importable without installing it (it has no setup.py)
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "satgenpy"))

C = 299792458.0
EARTH_RADIUS_M = 6371000.0  # spherical value, used only for the closed-form slant range


def db2lin(db):
    return 10.0 ** (db / 10.0)


def lin2db(x):
    return 10.0 * math.log10(x)


def dbm2w(dbm):
    return 10.0 ** ((dbm - 30.0) / 10.0)


def w2dbm(w):
    return 10.0 * math.log10(w) + 30.0


DEFAULT_PARAMS = {
    "freq_hz": 2e9,
    "altitude_m": 600e3,
    "g_rx_dbi": 36.0,          # satellite receive antenna
    "g_tx_dbi": 0.0,           # station antenna
    "p_rx_min_dbm": -120.0,    # receiver sensitivity
    "link_margin_db": 10.0,
    "p_tx_max_dbm": 23.0,      # 200 mW
    "pa_efficiency": 0.3,
    "p_circuit_w": 1e-3,
    "rate_bps": 1000.0,
    "slot_s": 1.0,
    "min_elevation_deg": 10.0,
}


def slant_range_m(elevation_deg, altitude_m=600e3, earth_radius_m=EARTH_RADIUS_M):
    """Closed-form distance station -> satellite on a spherical Earth."""
    e = math.radians(elevation_deg)
    r = earth_radius_m
    return math.sqrt((r + altitude_m) ** 2 - (r * math.cos(e)) ** 2) - r * math.sin(e)


def fspl_lin(distance_m, freq_hz):
    return (4.0 * math.pi * distance_m * freq_hz / C) ** 2


def required_tx_power_w(distance_m, p):
    """Tx power (W) needed so the satellite receives P_rx_min + margin."""
    d = np.asarray(distance_m, dtype=float)
    fspl = (4.0 * np.pi * d * p["freq_hz"] / C) ** 2
    gains = db2lin(p["g_tx_dbi"] + p["g_rx_dbi"])
    return dbm2w(p["p_rx_min_dbm"] + p["link_margin_db"]) * fspl / gains


def slot_energy_j(distance_m, p):
    """Energy (J) a station spends transmitting for one slot at this distance.
    Returns inf where the required power exceeds P_tx,max (slot unusable)."""
    ptx = required_tx_power_w(distance_m, p)
    e = (ptx / p["pa_efficiency"] + p["p_circuit_w"]) * p["slot_s"]
    return np.where(ptx <= dbm2w(p["p_tx_max_dbm"]), e, np.inf)


def baseline_link_budget(p_sat_w=200.0, g_sat_dbi=36.0, freq_hz=2e9, distance_m=600e3,
                         g_tag_dbi=0.0, tag_losses_db=3.0, reflection_db=-10.0):
    """Reproduces the book's first-model check (passive A-IoT tag powered from LEO).
    Tag gain / losses / reflection factor are assumptions, as in the original note."""
    fspl_db = lin2db(fspl_lin(distance_m, freq_hz))
    harvest_dbm = w2dbm(p_sat_w) + g_sat_dbi - fspl_db + g_tag_dbi - tag_losses_db
    gap_db = -30.0 - harvest_dbm  # 1 uW = -30 dBm
    backscatter_dbm = harvest_dbm + reflection_db + g_tag_dbi - fspl_db + g_sat_dbi
    return {"fspl_db": fspl_db, "harvest_dbm": harvest_dbm,
            "gap_to_1uW_db": gap_db, "backscatter_dbm": backscatter_dbm}


def geodetic_to_ecef(lat_deg, lon_deg, h_m):
    """WGS72 geodetic -> ECEF (vectorised), same ellipsoid as Hypatia/sgp4."""
    a = 6378135.0
    f = 1.0 / 298.26
    e2 = f * (2 - f)
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    n = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    x = (n + h_m) * np.cos(lat) * np.cos(lon)
    y = (n + h_m) * np.cos(lat) * np.sin(lon)
    z = (n * (1 - e2) + h_m) * np.sin(lat)
    return np.stack([x, y, z], axis=-1)


def up_vectors(lat_deg, lon_deg):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)
