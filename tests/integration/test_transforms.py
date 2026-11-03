"""SQL transforms on a tiny hand-built dataset where every expected answer is worked out by hand.

Everything runs inside a transaction that is rolled back, so real data is never touched.
"""

from decimal import Decimal

import pytest

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.load import connect
from tillflow_retail_etl.transform import run_transforms

# (invoice, stock_code, description, quantity, invoice_date, price, customer_id, country)
ROWS = [
    # Customer 11111: two purchase days, ten days apart
    ("100001", "10001", "WIDGET", 2, "2011-01-01 10:00", 5, "11111", "United Kingdom"),  # 10
    ("100001", "10002", "GADGET", 1, "2011-01-01 10:00", 10, "11111", "United Kingdom"),  # 10
    ("100002", "10002", "GADGET", 3, "2011-01-11 09:00", 10, "11111", "United Kingdom"),  # 30
    # Customer 22222: one purchase, with an exact duplicate line and a postage line
    ("100003", "10003", "BIG THING", 1, "2011-01-20 12:00", 100, "22222", "EIRE"),  # 100
    ("100003", "10003", "BIG THING", 1, "2011-01-20 12:00", 100, "22222", "EIRE"),  # duplicate
    ("100003", "POST", "POSTAGE", 1, "2011-01-20 12:00", 5, "22222", "EIRE"),  # not a product
    # A cancellation and a guest purchase
    ("C100004", "10002", "GADGET", -1, "2011-01-21 08:00", 10, "11111", "United Kingdom"),
    ("100005", "10004", "GIFT", 2, "2011-02-05 15:00", 25, None, "United Kingdom"),  # 50
]


@pytest.fixture
def db():
    """Swap raw data for the fixture, build every table, then roll it all back."""
    with connect(get_settings()) as conn:
        with conn.transaction(force_rollback=True):
            conn.execute("TRUNCATE raw.transactions")
            load_id = conn.execute(
                "INSERT INTO ops.load_log (source_blob, blob_etag, status) "
                "VALUES ('fixture', 'fixture', 'success') RETURNING load_id"
            ).fetchone()[0]
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO raw.transactions (invoice, stock_code, description, quantity, "
                    "invoice_date, price, customer_id, country, source_blob, load_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'fixture', %s)",
                    [(*row, load_id) for row in ROWS],
                )
            run_transforms(conn)
            yield conn


@pytest.mark.integration
def test_staging_removes_duplicates_and_cleans_countries(db):
    assert db.execute("SELECT COUNT(*) FROM staging.transactions").fetchone()[0] == 7
    ireland = db.execute(
        "SELECT COUNT(*) FROM staging.transactions WHERE country = 'Ireland'"
    ).fetchone()[0]
    assert ireland == 2  # EIRE renamed; duplicate removed


@pytest.mark.integration
def test_staging_classifies_rows(db):
    flags = db.execute(
        "SELECT COUNT(*) FILTER (WHERE is_cancellation), "
        "COUNT(*) FILTER (WHERE is_non_product), "
        "COUNT(*) FILTER (WHERE is_product_sale) "
        "FROM staging.transactions"
    ).fetchone()
    assert flags == (1, 1, 5)


@pytest.mark.integration
def test_monthly_revenue(db):
    rows = db.execute(
        "SELECT month::text, revenue, orders, mom_change_pct, is_partial_month "
        "FROM marts.monthly_revenue ORDER BY month"
    ).fetchall()
    assert rows == [
        ("2011-01-01", Decimal("150.00"), 3, None, False),
        ("2011-02-01", Decimal("50.00"), 1, Decimal("-66.7"), True),
    ]


@pytest.mark.integration
def test_customer_rfm(db):
    rows = db.execute(
        "SELECT customer_id, recency_days, frequency, monetary "
        "FROM marts.customer_rfm ORDER BY customer_id"
    ).fetchall()
    # As-of date = 2011-02-06 (day after the last transaction)
    assert rows == [
        ("11111", 26, 2, Decimal("50.00")),
        ("22222", 17, 1, Decimal("100.00")),  # duplicate not double-counted
    ]


@pytest.mark.integration
def test_customer_purchase_gaps(db):
    rows = db.execute(
        "SELECT customer_id, purchase_days, mean_gap_days "
        "FROM marts.customer_purchase_gaps ORDER BY customer_id"
    ).fetchall()
    assert rows == [("11111", 2, Decimal("10.0")), ("22222", 1, None)]


@pytest.mark.integration
def test_revenue_reconciles_between_staging_and_marts(db):
    matches = db.execute(
        "SELECT (SELECT SUM(revenue) FROM marts.monthly_revenue) = "
        "(SELECT SUM(line_revenue) FROM staging.transactions WHERE is_product_sale)"
    ).fetchone()[0]
    assert matches
