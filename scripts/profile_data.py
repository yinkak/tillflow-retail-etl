"""Profile the landing CSVs to find data-quality issues before writing validation rules."""

from pathlib import Path

import pandas as pd

FILES = sorted(Path("data/landing").glob("*.csv.gz"))


def load() -> pd.DataFrame:
    frames = [pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""]) for f in FILES]
    return pd.concat(frames, ignore_index=True)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def shape_of(series: pd.Series) -> pd.Series:
    """Turn values into patterns: digits -> 9, letters -> A (e.g. 'C489434' -> 'A999999')."""
    return series.str.replace(r"\d", "9", regex=True).str.replace(r"[A-Za-z]", "A", regex=True)


def main() -> None:
    df = load()
    invoice = df["Invoice"]
    is_cancellation = invoice.str.startswith("C", na=False)

    section("Shape")
    print(f"{len(df):,} rows, columns: {list(df.columns)}")

    section("Missing values per column")
    print(df.isna().sum().to_string())

    section("Exact duplicate rows")
    print(f"{df.duplicated().sum():,}")

    section("Invoice patterns")
    print(shape_of(invoice).value_counts().to_string())

    quantity = pd.to_numeric(df["Quantity"], errors="coerce")
    section("Quantity")
    print(f"not a number:                         {quantity.isna().sum():,}")
    print(f"zero:                                 {(quantity == 0).sum():,}")
    print(f"negative:                             {(quantity < 0).sum():,}")
    print(f"negative on NON-cancellation invoices: {((quantity < 0) & ~is_cancellation).sum():,}")

    price = pd.to_numeric(df["Price"], errors="coerce")
    section("Price")
    print(f"not a number: {price.isna().sum():,}")
    print(f"zero:         {(price == 0).sum():,}")
    print(f"negative:     {(price < 0).sum():,}")

    dates = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    section("InvoiceDate")
    print(f"unparseable: {dates.isna().sum():,}")
    print(f"range:       {dates.min()} -> {dates.max()}")

    section("StockCode patterns (top 15)")
    print(shape_of(df["StockCode"]).value_counts().head(15).to_string())

    section("Most common StockCodes that aren't 5 digits (+ optional letters)")
    unusual = df.loc[~df["StockCode"].str.fullmatch(r"\d{5}[A-Za-z]*", na=False), "StockCode"]
    print(unusual.value_counts().head(15).to_string())

    section("Customer ID formats")
    print(shape_of(df["Customer ID"].dropna()).value_counts().to_string())

    section("Country")
    print(f"{df['Country'].nunique()} distinct; top 5:")
    print(df["Country"].value_counts().head(5).to_string())

    section("Sample rows with zero or negative price")
    print(df[price <= 0].head(10).to_string())


if __name__ == "__main__":
    main()
