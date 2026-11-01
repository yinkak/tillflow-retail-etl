"""One-time conversion: Online Retail II Excel -> two gzipped CSVs (one per year).

Values are kept as text and nothing is cleaned here. Raw data stays untouched;
validation happens later in the pipeline.
"""

import argparse
from pathlib import Path

import pandas as pd

SHEETS = {
    "Year 2009-2010": "online_retail_2009_2010.csv.gz",
    "Year 2010-2011": "online_retail_2010_2011.csv.gz",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/online_retail_II.xlsx"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/landing"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading {args.input} (this can take a couple of minutes)...")
    sheets = pd.read_excel(args.input, sheet_name=list(SHEETS), dtype=str, engine="openpyxl")

    total = 0
    for sheet, filename in SHEETS.items():
        df = sheets[sheet]
        out_path = args.out_dir / filename
        df.to_csv(out_path, index=False, compression="gzip")
        total += len(df)
        print(f"{sheet}: {len(df):,} rows -> {out_path}")

    print(f"Total: {total:,} rows")


if __name__ == "__main__":
    main()
