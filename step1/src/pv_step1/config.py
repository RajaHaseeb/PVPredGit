"""Configuration for PV load / clean / irradiance→power conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# step1/src/pv_step1/config.py -> PV Pred/
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_PARENT = PROJECT_ROOT.parent
DATA_BASE = WORKSPACE_PARENT / "Data Base"
LOCAL_DATA = PROJECT_ROOT / "data_sources"


@dataclass(frozen=True)
class Step1Config:
    """Immutable PV Step 1 settings."""

    input_file: Path = LOCAL_DATA / "10 Year CAMS Saint Nazaire Data_clean.xlsx"
    output_dir: Path = PROJECT_ROOT / "step1" / "outputs"

    site_lat: float = 47.27
    site_lon: float = -2.21
    site_alt_m: float = 5.0
    site_tz: str = "UTC"

    pv_tilt_deg: float = 30.0
    pv_azimuth_deg: float = 180.0
    pv_albedo: float = 0.20
    pv_system_capacity_kwp: float = 2500.0
    pv_module_power_w: float = 625.0
    pv_gamma_pmp_per_c: float = -0.0026
    pv_noct_c: float = 45.0
    pv_dc_derate: float = 1.0
    pv_bifaciality: float = 0.70
    pv_rear_irrad_fraction: float = 0.0
    pv_default_air_temp_c: float = 15.0
    # Recompute from irradiance whenever GHI/DHI/DNI exist (even if a power column is present).
    pv_recompute_from_irradiance: bool = True

    year_range: tuple[int, int] | None = None
    enable_plots: bool = True
