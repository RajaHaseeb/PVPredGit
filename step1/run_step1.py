"""PV Pred Step 1 entry point — load Data Base CAMS, clean, convert to power.

HOW TO RUN
----------
    python run_step1.py
    python run_step1.py --year-start 2015 --year-end 2024
"""

from pathlib import Path
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    from pv_step1.pipeline import main  # type: ignore


if __name__ == "__main__":
    main()
