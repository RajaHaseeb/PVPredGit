from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True)
class PVSystemConfig:
    capacity_kw: float = 1.0
    surface_tilt: float = 30.0
    surface_azimuth: float = 180.0
    gamma_pdc: float = -0.003


def generate_pv_power_timeseries(
    *,
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    frequency: str = "1h",
    timezone: str = "UTC",
    config: Optional[PVSystemConfig] = None,
    temp_air_c: float = 25.0,
    wind_speed_mps: float = 1.0,
) -> "pd.DataFrame":
    """
    Generate a photovoltaic power time-series using pvlib clear-sky modeling.
    """
    try:
        import pvlib
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "pvlib is required. Install with `pip install pvlib`."
        ) from exc
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "pandas is required. Install with `pip install pandas`."
        ) from exc

    cfg = config or PVSystemConfig()
    location = pvlib.location.Location(latitude=latitude, longitude=longitude, tz=timezone)
    times = pd.date_range(start=start, end=end, freq=frequency, tz=timezone, inclusive="left")

    solar_position = location.get_solarposition(times)
    clearsky = location.get_clearsky(times)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=cfg.surface_tilt,
        surface_azimuth=cfg.surface_azimuth,
        dni=clearsky["dni"],
        ghi=clearsky["ghi"],
        dhi=clearsky["dhi"],
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
    )

    temp_cell = pvlib.temperature.sapm_cell(
        poa_global=poa["poa_global"],
        temp_air=temp_air_c,
        wind_speed=wind_speed_mps,
    )
    pdc = pvlib.pvsystem.pvwatts_dc(
        g_poa_effective=poa["poa_global"],
        temp_cell=temp_cell,
        pdc0=cfg.capacity_kw * 1000.0,
        gamma_pdc=cfg.gamma_pdc,
    )

    power_kw = pdc.clip(lower=0) / 1000.0
    return pd.DataFrame(
        {
            "power_kw": power_kw,
            "poa_global_wm2": poa["poa_global"],
            "apparent_zenith_deg": solar_position["apparent_zenith"],
        },
        index=times,
    )
