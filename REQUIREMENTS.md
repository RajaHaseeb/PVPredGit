# PV Pred — Step 1 requirements

Load CAMS / solar irradiance from **Data Base**, clean it, and convert to hourly PV power (kW).

## Install

```powershell
pip install -r requirements.txt
```

## Required libraries

| Library | Used for |
|---------|----------|
| **numpy** | Arrays and numeric transforms |
| **pandas** | CSV/XLSX I/O and hourly tables |
| **pvlib** | Solar position, POA irradiance, PV power model |
| **openpyxl** | Reading Excel CAMS archives |
| **matplotlib** | Optional overview plots |

## Quick run

```powershell
cd "PV Pred\step1"
python run_step1.py
```

Outputs land in `step1/outputs/` (`step1_pv_hourly.csv`, `step1_summary.json`).
