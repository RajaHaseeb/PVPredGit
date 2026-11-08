"""PV Step 1 pipeline: CLI → load/clean/convert → write outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from pv_step1.config import LOCAL_DATA, PROJECT_ROOT, Step1Config
from pv_step1.convert import filter_year_range, load_and_convert_pv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load CAMS PV data from Data Base, clean it, and convert irradiance to power (kW)."
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=LOCAL_DATA / "10 Year CAMS Saint Nazaire Data_clean.xlsx",
        help="Raw or cleaned CAMS PV source (CSV/XLSX under PV Pred/data_sources or Data Base).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "step1" / "outputs",
        help="Folder for step1_pv_hourly.csv and summary JSON.",
    )
    parser.add_argument("--site-lat", type=float, default=47.27)
    parser.add_argument("--site-lon", type=float, default=-2.21)
    parser.add_argument("--site-alt-m", type=float, default=5.0)
    parser.add_argument("--site-tz", type=str, default="UTC")
    parser.add_argument("--pv-tilt-deg", type=float, default=30.0)
    parser.add_argument("--pv-azimuth-deg", type=float, default=180.0)
    parser.add_argument("--pv-system-capacity-kwp", type=float, default=2500.0)
    parser.add_argument("--pv-module-power-w", type=float, default=625.0)
    parser.add_argument("--year-start", type=int, default=None)
    parser.add_argument("--year-end", type=int, default=None)
    parser.add_argument(
        "--use-existing-power",
        action="store_true",
        help="Prefer an existing power column instead of recomputing from irradiance.",
    )
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Step1Config:
    year_range = None
    if args.year_start is not None and args.year_end is not None:
        year_range = (int(args.year_start), int(args.year_end))
    return Step1Config(
        input_file=Path(args.input_file),
        output_dir=Path(args.output_dir),
        site_lat=float(args.site_lat),
        site_lon=float(args.site_lon),
        site_alt_m=float(args.site_alt_m),
        site_tz=str(args.site_tz),
        pv_tilt_deg=float(args.pv_tilt_deg),
        pv_azimuth_deg=float(args.pv_azimuth_deg),
        pv_system_capacity_kwp=float(args.pv_system_capacity_kwp),
        pv_module_power_w=float(args.pv_module_power_w),
        pv_recompute_from_irradiance=not bool(args.use_existing_power),
        year_range=year_range,
        enable_plots=not bool(args.no_plots),
    )


def _safe_to_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        alt = path.with_name(f"{path.stem}_alt.csv")
        df.to_csv(alt, index=False)
        return alt


def _write_overview_plot(df: pd.DataFrame, path: Path, cfg: Step1Config) -> Path | None:
    if not cfg.enable_plots or df.empty:
        return None
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    work = df.sort_values("timestamp_utc").head(24 * 14).copy()
    ts = pd.to_datetime(work["timestamp_utc"], utc=True, errors="coerce")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(ts, work["pv_power_kw"], color="tab:orange", lw=1.0)
    ax.set_title(f"PV power preview ({cfg.pv_system_capacity_kwp:g} kWp)")
    ax.set_ylabel("pv_power_kw")
    ax.set_xlabel("timestamp_utc")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def run_step1(cfg: Step1Config) -> dict[str, Path | object]:
    pv, source_path = load_and_convert_pv(cfg)
    pv, window_note = filter_year_range(pv, cfg.year_range)
    pv = pv.sort_values("timestamp_utc").drop_duplicates("timestamp_utc", keep="first")

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hourly_path = _safe_to_csv(pv, out_dir / "step1_pv_hourly.csv")

    ts = pd.to_datetime(pv["timestamp_utc"], utc=True, errors="coerce")
    n_days = int(ts.dt.floor("D").nunique()) if not ts.empty else 0
    summary = {
        "source_path": str(source_path),
        "output_csv": str(hourly_path),
        "rows": int(len(pv)),
        "distinct_utc_days": n_days,
        "utc_start": ts.min().isoformat() if not ts.empty else None,
        "utc_end": ts.max().isoformat() if not ts.empty else None,
        "mean_pv_power_kw": float(pd.to_numeric(pv["pv_power_kw"], errors="coerce").mean()),
        "max_pv_power_kw": float(pd.to_numeric(pv["pv_power_kw"], errors="coerce").max()),
        "pv_system_capacity_kwp": cfg.pv_system_capacity_kwp,
        "year_filter": window_note,
    }
    summary_path = out_dir / "step1_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    plot_path = _write_overview_plot(pv, out_dir / "step1_pv_overview.png", cfg)
    report_path = out_dir / "step1_report.txt"
    report_path.write_text(
        "\n".join(
            [
                "PV Pred — Step 1",
                f"Source: {source_path}",
                f"Output: {hourly_path}",
                f"Rows: {len(pv)}",
                f"Distinct UTC days: {n_days}",
                f"Year filter: {window_note}",
                f"Mean power: {summary['mean_pv_power_kw']:.3f} kW",
                f"Max power: {summary['max_pv_power_kw']:.3f} kW",
                f"Plot: {plot_path if plot_path else 'skipped'}",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "hourly_csv": hourly_path,
        "summary_json": summary_path,
        "report_txt": report_path,
        "plot": plot_path,
        "summary": summary,
    }


def main() -> None:
    cfg = build_config(parse_args())
    result = run_step1(cfg)
    summary = result["summary"]
    assert isinstance(summary, dict)
    print("--- PV Pred Step 1 ---")
    print(f"  Source:  {summary['source_path']}")
    print(f"  Output:  {result['hourly_csv']}")
    print(f"  Rows:    {summary['rows']}  ({summary['distinct_utc_days']} days)")
    print(f"  Filter:  {summary['year_filter']}")
    print(f"  Mean kW: {summary['mean_pv_power_kw']:.3f}")
    print("----------------------")


if __name__ == "__main__":
    main()
