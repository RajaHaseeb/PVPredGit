# PVPredGit

Minimal Python utilities for **solar photovoltaic (PV) time-series** modeling with **pvlib**.

## Example

```python
from pv_timeseries import generate_pv_power_timeseries

df = generate_pv_power_timeseries(
    latitude=35.0,
    longitude=-120.0,
    start="2026-01-01 00:00",
    end="2026-01-02 00:00",
    frequency="15min",
)
print(df.head())
```

Install dependency:

```bash
pip install pvlib pandas
```
