# Data Base

Put the raw meteo archives here (shared by PV Pred and Wind Pred):

| File | Used by |
|------|---------|
| `10 Year CAMS Saint Nazaire Data_clean.xlsx` | PV Pred |
| `10 Year CAMS Saint Nazaire Data_hourly_clean.csv` | PV Pred (alt) |
| `10 Year NOAA MonTOIR Data_hourly_clean.csv` | Wind Pred |
| `10 Year NOAA MonTOIR Data.csv` | Wind Pred (alt / temperature) |

After copying the files, run:

```powershell
python "PV Pred\step1\run_step1.py"
python "Wind Pred\step1\run_step1.py"
```
