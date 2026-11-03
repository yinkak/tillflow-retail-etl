"""Validation rules: each rule rejects broken data and allows valid-but-unusual data."""

import pandas as pd
import pytest

from tillflow_retail_etl.validate import split_valid_invalid

VALID_ROW = {
    "Invoice": "489434",
    "StockCode": "85048",
    "Description": "15CM CHRISTMAS GLASS BALL",
    "Quantity": "12",
    "InvoiceDate": "2009-12-01 07:45:00",
    "Price": "6.95",
    "Customer ID": "13085",
    "Country": "United Kingdom",
}


def make(**overrides: object) -> pd.DataFrame:
    return pd.DataFrame([{**VALID_ROW, **overrides}])


def test_valid_row_passes_with_proper_types():
    valid, quarantine = split_valid_invalid(make())

    assert len(valid) == 1
    assert quarantine.empty
    assert valid["quantity"].iloc[0] == 12
    assert valid["price"].iloc[0] == pytest.approx(6.95)


@pytest.mark.parametrize(
    "overrides",
    [
        {"Invoice": "C489434", "Quantity": "-12"},  # cancellation
        {"Invoice": "A506401", "Price": "-53594.36", "StockCode": "B"},  # bad-debt adjustment
        {"Customer ID": None},  # guest purchase
        {"Description": None},  # adjustment rows often lack a description
        {"Price": "0"},  # free item
        {"StockCode": "POST"},  # postage line
    ],
)
def test_valid_but_unusual_rows_pass(overrides):
    valid, quarantine = split_valid_invalid(make(**overrides))

    assert len(valid) == 1
    assert quarantine.empty


@pytest.mark.parametrize(
    ("overrides", "expected_in_reason"),
    [
        ({"Invoice": "X489434"}, "invoice"),
        ({"Invoice": "48943"}, "invoice"),
        ({"Quantity": "0"}, "quantity"),
        ({"Quantity": "twelve"}, "quantity"),
        ({"InvoiceDate": "not a date"}, "invoice_date"),
        ({"Customer ID": "130"}, "customer_id"),
        ({"Country": ""}, "country"),
        ({"Price": "-1.00"}, "price"),
    ],
)
def test_broken_rows_are_quarantined_with_a_reason(overrides, expected_in_reason):
    valid, quarantine = split_valid_invalid(make(**overrides))

    assert valid.empty
    assert len(quarantine) == 1
    assert expected_in_reason in quarantine["reason"].iloc[0]


def test_every_row_is_either_valid_or_quarantined():
    chunk = pd.concat(
        [make(), make(Quantity="0"), make(), make(Invoice="bad"), make()], ignore_index=True
    )

    valid, quarantine = split_valid_invalid(chunk)

    assert len(valid) == 3
    assert len(quarantine) == 2
    assert len(valid) + len(quarantine) == len(chunk)
