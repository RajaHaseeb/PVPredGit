# PVPredGit

PV forecasting project for cleaning CAMS solar-irradiance data and converting it to hourly photovoltaic power.

PV forecasting project for cleaning CAMS solar-irradiance data and converting it to hourly photovoltaic power.

## Setup

```powershell
pip install -r requirements.txt
```

## Run Step 1

Place the required CAMS input data in `data_sources/`, then run:

```powershell
python step1/run_step1.py
```

Generated hourly power data and reports are written to `step1/outputs/` and are intentionally excluded from Git.
