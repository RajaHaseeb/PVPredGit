"""I/O helpers: resolve Data Base paths and read CAMS CSV/XLSX tables."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from pv_step1.config import DATA_BASE, LOCAL_DATA, PROJECT_ROOT, WORKSPACE_PARENT


_PRIORITY_NAMES = [
    "10 Year CAMS Saint Nazaire Data_hourly_clean.csv",
    "10 Year CAMS Saint Nazaire Data_hourly_clean.xlsx",
    "10 Year CAMS Saint Nazaire Data_clean.xlsx",
    "10 Year CAMS Saint Nazaire Data.csv",
]


def resolve_input_path(path: Path, priority_names: list[str] | None = None) -> Path:
    """Resolve a PV source path under ``Data Base`` or ``PV Pred/data_sources``."""
    names = list(priority_names or []) + list(_PRIORITY_NAMES)
    search_dirs = [
        DATA_BASE,
        LOCAL_DATA,
        PROJECT_ROOT,
        WORKSPACE_PARENT,
        WORKSPACE_PARENT / "Scenario Clustering Python" / "Data Base",
        Path.cwd(),
    ]
    candidates: list[Path] = []

    def push(p: Path) -> None:
        if p.is_absolute():
            candidates.append(p)
            return
        for root in search_dirs:
            candidates.append((root / p).resolve())
            candidates.append((root / Path(p).name).resolve())

    push(Path(path))
    for name in names:
        if not name:
            continue
        name_path = Path(name)
        if name_path.is_absolute():
            candidates.append(name_path)
        else:
            push(name_path)

    seen: set[str] = set()
    unique: list[Path] = []
    for p in candidates:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    for p in unique:
        if p.exists():
            return p

    expected = "10 Year CAMS Saint Nazaire Data_clean.xlsx"
    raise FileNotFoundError(
        "Could not locate the CAMS PV input file.\n"
        f"  Place `{expected}` (or hourly_clean CSV/XLSX) in one of:\n"
        f"    - {DATA_BASE}\n"
        f"    - {LOCAL_DATA}\n"
        "  Or pass an absolute path:  python run_step1.py --input-file \"D:\\path\\to\\file.xlsx\"\n"
        "Tried:\n  - " + "\n  - ".join(str(p) for p in unique[:12])
    )


def find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    def _norm(name: str) -> str:
        return name.strip().lstrip("\ufeff").lower()

    lower_map = {_norm(str(c)): c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
        key = _norm(c)
        if key in lower_map:
            return lower_map[key]
    return None


def read_table(path: Path) -> pd.DataFrame:
    """Read CSV/XLSX and normalize column names."""
    ext = path.suffix.lower()
    if ext == ".csv":
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        header_idx = None
        for idx, line in enumerate(lines):
            if "Observation period" in line and ";" in line:
                header_idx = idx
                break

        if header_idx is not None:
            header_line = lines[header_idx].lstrip("# ")
            buf = "\n".join([header_line] + lines[header_idx + 1 :])
            df = pd.read_csv(io.StringIO(buf), sep=";", comment="#")
        else:
            parse_attempts = [
                {"comment": "#", "sep": None, "engine": "python"},
                {"comment": "#", "sep": ";", "engine": "python"},
                {"comment": "#", "sep": ",", "engine": None},
                {"comment": None, "sep": None, "engine": "python"},
            ]
            last_err: Exception | None = None
            for opts in parse_attempts:
                try:
                    df = pd.read_csv(path, **{k: v for k, v in opts.items() if v is not None})
                    if len(df.columns) == 1:
                        only_col = str(df.columns[0])
                        if (";" in only_col and opts.get("sep") == ",") or (
                            "," in only_col and opts.get("sep") == ";"
                        ):
                            continue
                        if "," in only_col and opts.get("sep") is None:
                            continue
                    break
                except pd.errors.ParserError as exc:
                    last_err = exc
                    continue
            else:
                raise last_err if last_err else ValueError(f"Could not parse CSV: {path}")
    elif ext in {".xlsx", ".xls"}:
        if "solar_clean" in pd.ExcelFile(path).sheet_names:
            df = pd.read_excel(path, sheet_name="solar_clean")
        else:
            df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported PV file format: {ext}")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_timestamp(series: pd.Series) -> pd.Series:
    """Parse timestamps; CAMS period strings ``start/end`` use the start time."""
    s = series.astype(str)
    if s.str.contains("/").any():
        parts = s.str.split("/", n=1, expand=True)
        return pd.to_datetime(parts[0], errors="coerce", utc=True)
    return pd.to_datetime(s, errors="coerce", utc=True)


_AMBIENT_TEMP_COLUMN_CANDIDATES = [
    "air_temp_c",
    "temp_c",
    "ambient_temp_c",
    "t_amb_c",
    "temperature_c",
    "temperature_2m",
    "temperature_2m_c",
    "t2m",
    "t2m_c",
    "2m_temperature",
    "2m_temperature_c",
    "ta",
    "temp_air_c",
    "air_temperature_c",
    "t_air_c",
    "temp_2m_c",
    "temp_2m",
]


def find_ambient_temp_column(df: pd.DataFrame) -> str | None:
    hit = find_first_existing(df, _AMBIENT_TEMP_COLUMN_CANDIDATES)
    if hit is not None:
        return hit
    for col in df.columns:
        name = str(col).strip().lstrip("\ufeff").lower()
        if "temp" not in name:
            continue
        if any(tok in name for tok in ("2m", "air", "ambient", "t2m", "t_amb")):
            return str(col)
    return None


def parse_noaa_tmp_series(tmp: pd.Series) -> pd.Series:
    """Parse NOAA-style TMP values, e.g. ``+0123,1`` -> 12.3 °C."""

    def parse_one(x: object) -> float:
        if pd.isna(x):
            return float("nan")
        token = str(x).split(",", 1)[0].strip()
        if not token:
            return float("nan")
        try:
            val = int(token)
        except ValueError:
            return float("nan")
        if abs(val) >= 9999:
            return float("nan")
        return val / 10.0

    return tmp.map(parse_one)


def extract_ambient_temp_c(df: pd.DataFrame, default_c: float) -> pd.Series:
    ambient_col = find_ambient_temp_column(df)
    if ambient_col is not None:
        return pd.to_numeric(df[ambient_col], errors="coerce")
    if "TMP" in df.columns:
        return parse_noaa_tmp_series(df["TMP"])
    return pd.Series(float("nan"), index=df.index, dtype=float)
