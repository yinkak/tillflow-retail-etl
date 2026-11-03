"""Validate: check each row against the schema and split good rows from bad ones.

Rules reject *broken* data. Valid-but-unusual rows (cancellations, stock write-offs,
bad-debt adjustments, postage codes) pass through and are classified later in SQL.
"""

import pandas as pd
import pandera.pandas as pa

COLUMN_NAMES = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}

SCHEMA = pa.DataFrameSchema(
    {
        # 6 digits, optionally prefixed C (cancellation) or A (accounting adjustment)
        "invoice": pa.Column(str, pa.Check.str_matches(r"^[CA]?\d{6}$")),
        "stock_code": pa.Column(str, pa.Check.str_length(min_value=1)),
        "description": pa.Column(str, nullable=True),
        "quantity": pa.Column(int, pa.Check.ne(0)),
        "invoice_date": pa.Column("datetime64[ns]"),
        "price": pa.Column(float),
        "customer_id": pa.Column(str, pa.Check.str_matches(r"^\d{5}$"), nullable=True),
        "country": pa.Column(str, pa.Check.str_length(min_value=1)),
    },
    checks=pa.Check(
        lambda df: (df["price"] >= 0) | df["invoice"].str.startswith("A"),
        name="price_non_negative_unless_adjustment",
        error="price is negative on a non-adjustment invoice",
    ),
    coerce=True,
    strict=True,
)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename source columns to snake_case."""
    return df.rename(columns=COLUMN_NAMES)


def split_valid_invalid(chunk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (valid rows with proper types, quarantined rows with a `reason` column)."""
    df = standardize_columns(chunk)
    try:
        return SCHEMA.validate(df, lazy=True), _empty_quarantine(df)
    except pa.errors.SchemaErrors as err:
        failures = err.failure_cases.dropna(subset=["index"])
        if failures.empty:
            raise  # a problem with the whole file (e.g. a missing column), not with rows

        failures = failures.assign(
            index=failures["index"].astype("int64"),
            reason=failures["column"].fillna("row").astype(str)
            + ": "
            + failures["check"].astype(str),
        )
        reasons = failures.groupby("index")["reason"].agg(lambda r: "; ".join(sorted(set(r))))

        quarantine = df.loc[reasons.index].assign(reason=reasons.to_numpy())
        valid = SCHEMA.validate(df.drop(index=reasons.index))  # raises if anything else is wrong
        return valid, quarantine


def _empty_quarantine(df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[0:0].assign(reason=pd.Series(dtype=str))
