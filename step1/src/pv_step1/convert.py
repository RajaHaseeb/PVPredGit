"""Load PV source data and convert irradiance to DC power (kW)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pv_step1.config import Step1Config
from pv_step1.io import (
    extract_ambient_temp_c,
    find_first_existing,
    parse_timestamp,
    read_table,
    resolve_input_path,
)


def compute_pv_from_irradiance(df: pd.DataFrame, ts_col: str, cfg: Step1Config) -> pd.DataFrame:
    """Convert raw irradiance to PV power using site geometry + system assumptions."""
    try:
        import pvlib  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pvlib is required for irradiance → PV power conversion. "
            "Install with: pip install pvlib"
        ) from exc

    ghi_col = find_first_existing(df, ["ghi_w_m2", "ghi_wh_m2", "ghi", "GHI"])
    dhi_col = find_first_existing(df, ["dhi_w_m2", "dhi_wh_m2", "dhi", "DHI"])
    dni_col = find_first_existing(
        df, ["dni_w_m2", "dni_wh_m2", "bni_w_m2", "bni_wh_m2", "dni", "bni", "BNI"]
    )
    if not all([ghi_col, dhi_col, dni_col]):
        raise ValueError(
            "PV file lacks irradiance columns. Expected ghi_*, dhi_*, dni_* (or bni_*)."
        )

    ghi = pd.to_numeric(df[ghi_col], errors="coerce")
    dhi = pd.to_numeric(df[dhi_col], errors="coerce")
    dni = pd.to_numeric(df[dni_col], errors="coerce")
    air_temp_c = extract_ambient_temp_c(df, cfg.pv_default_air_temp_c).fillna(
        cfg.pv_default_air_temp_c
    )

    timestamp_utc = parse_timestamp(df[ts_col])
    midpoint_local = (timestamp_utc + pd.Timedelta(minutes=30)).dt.tz_convert(cfg.site_tz)

    location = pvlib.location.Location(
        cfg.site_lat, cfg.site_lon, tz=cfg.site_tz, altitude=cfg.site_alt_m
    )
    solpos = location.get_solarposition(midpoint_local)
    sun_up = solpos["apparent_zenith"].to_numpy() < 90.0
    dni_extra = pvlib.irradiance.get_extra_radiation(midpoint_local.dt.dayofyear.to_numpy())

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=cfg.pv_tilt_deg,
        surface_azimuth=cfg.pv_azimuth_deg,
        solar_zenith=solpos["apparent_zenith"].to_numpy(),
        solar_azimuth=solpos["azimuth"].to_numpy(),
        dni=dni.to_numpy(dtype=float),
        ghi=ghi.to_numpy(dtype=float),
        dhi=dhi.to_numpy(dtype=float),
        dni_extra=dni_extra,
        albedo=cfg.pv_albedo,
        model="perez",
    )

    poa_front = np.clip(poa["poa_global"], 0.0, None)
    poa_rear = cfg.pv_rear_irrad_fraction * poa_front
    poa_effective_raw = poa_front + cfg.pv_bifaciality * poa_rear
    poa_effective = np.where(sun_up, poa_effective_raw, 0.0)

    cell_temp_c = air_temp_c.to_numpy(dtype=float) + ((cfg.pv_noct_c - 20.0) / 800.0) * poa_effective
    temp_factor = 1.0 + cfg.pv_gamma_pmp_per_c * (cell_temp_c - 25.0)
    pdc_kw = cfg.pv_system_capacity_kwp * (poa_effective / 1000.0) * temp_factor * cfg.pv_dc_derate
    pv_power_kw = pd.Series(pdc_kw, index=df.index).where(sun_up, 0.0).clip(lower=0.0)
    pv_module_count = (
        (cfg.pv_system_capacity_kwp * 1000.0) / cfg.pv_module_power_w
        if cfg.pv_module_power_w > 0
        else np.nan
    )

    out = pd.DataFrame(
        {
            "timestamp_utc": timestamp_utc,
            "pv_power_kw": pv_power_kw,
            "ghi_w_m2": ghi,
            "dhi_w_m2": dhi,
            "dni_w_m2": dni,
            "poa_effective_w_m2": poa_effective,
            "air_temp_c": air_temp_c.to_numpy(dtype=float),
            "cell_temp_c": cell_temp_c,
            "assumption_pv_system_kwp": cfg.pv_system_capacity_kwp,
            "assumption_pv_module_power_w": cfg.pv_module_power_w,
            "assumption_pv_module_count": pv_module_count,
            "assumption_pv_tilt_deg": cfg.pv_tilt_deg,
            "assumption_pv_azimuth_deg": cfg.pv_azimuth_deg,
            "assumption_pv_albedo": cfg.pv_albedo,
            "assumption_pv_gamma_pmp_per_c": cfg.pv_gamma_pmp_per_c,
            "assumption_pv_noct_c": cfg.pv_noct_c,
            "assumption_pv_dc_derate": cfg.pv_dc_derate,
            "assumption_pv_bifaciality": cfg.pv_bifaciality,
            "assumption_pv_rear_irrad_fraction": cfg.pv_rear_irrad_fraction,
        }
    )
    return out.dropna(subset=["timestamp_utc", "pv_power_kw"]).copy()


def load_and_convert_pv(cfg: Step1Config) -> tuple[pd.DataFrame, Path]:
    """
    Load PV source and standardize to ``timestamp_utc``, ``pv_power_kw``.

    Modes:
      1) Precomputed power column (pv_power_kw / pdc_system_kw / …)
      2) Raw irradiance (ghi/dhi/dni) converted with site geometry
    """
    pv_path = resolve_input_path(cfg.input_file, [cfg.input_file.name])
    df = read_table(pv_path)

    ts_col = find_first_existing(
        df,
        [
            "timestamp_start_utc",
            "timestamp_utc",
            "timestamp",
            "DATE",
            "Observation period",
        ],
    )
    if ts_col is None:
        raise ValueError("Could not find PV timestamp column.")

    power_col = find_first_existing(
        df,
        [
            "pv_power_kw",
            "pdc_system_kw",
            "ac_power_kw",
            "solar_power_kw",
            "power_kw",
            "pdc_kw",
            "pv_power",
        ],
    )

    if cfg.pv_recompute_from_irradiance:
        try:
            return compute_pv_from_irradiance(df, ts_col, cfg), pv_path
        except ImportError:
            if power_col is None:
                raise
        except ValueError:
            if power_col is None:
                raise

    if power_col is not None:
        ts = parse_timestamp(df[ts_col])
        power = pd.to_numeric(df[power_col], errors="coerce")
        out_cols: dict[str, object] = {
            "timestamp_utc": ts,
            "pv_power_kw": power,
            "assumption_pv_system_kwp": cfg.pv_system_capacity_kwp,
            "assumption_pv_module_power_w": cfg.pv_module_power_w,
            "assumption_pv_tilt_deg": cfg.pv_tilt_deg,
            "assumption_pv_azimuth_deg": cfg.pv_azimuth_deg,
            "assumption_pv_albedo": cfg.pv_albedo,
        }
        air_temp = extract_ambient_temp_c(df, cfg.pv_default_air_temp_c)
        if air_temp.notna().any():
            out_cols["air_temp_c"] = air_temp
        out = pd.DataFrame(out_cols)
        out = out.dropna(subset=["timestamp_utc", "pv_power_kw"]).copy()
        out["pv_power_kw"] = out["pv_power_kw"].clip(lower=0.0)

        try:
            import pvlib  # type: ignore

            location = pvlib.location.Location(
                cfg.site_lat, cfg.site_lon, tz=cfg.site_tz, altitude=cfg.site_alt_m
            )
            midpoint_local = (out["timestamp_utc"] + pd.Timedelta(minutes=30)).dt.tz_convert(
                cfg.site_tz
            )
            solpos = location.get_solarposition(midpoint_local)
            sun_up = solpos["apparent_zenith"] < 90.0
            out.loc[~sun_up, "pv_power_kw"] = 0.0
        except Exception:
            pass

        return out, pv_path

    return compute_pv_from_irradiance(df, ts_col, cfg), pv_path


def filter_year_range(
    df: pd.DataFrame,
    year_range: tuple[int, int] | None,
) -> tuple[pd.DataFrame, str]:
    if year_range is None or df.empty or "timestamp_utc" not in df.columns:
        return df, "all available years"

    start_year, end_year = int(year_range[0]), int(year_range[1])
    out = df.copy()
    ts = pd.to_datetime(out["timestamp_utc"], errors="coerce")
    valid = ts.notna()
    if not valid.any():
        return out, f"requested {start_year}–{end_year}, skipped (no valid timestamps)"

    keep = valid & (ts.dt.year >= start_year) & (ts.dt.year <= end_year)
    out = out.loc[keep].copy()
    return out, f"calendar year range {start_year}–{end_year} (inclusive); rows={len(out)}"
