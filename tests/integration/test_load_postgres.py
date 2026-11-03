"""Load against real Postgres: idempotent reruns, replacement, rollback and quarantine."""

import uuid

import pandas as pd
import pytest

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.load import already_loaded, connect, load_file, mark_failed, start_load
from tillflow_retail_etl.validate import split_valid_invalid

ROW = {
    "Invoice": "489434",
    "StockCode": "85048",
    "Description": "15CM CHRISTMAS GLASS BALL",
    "Quantity": "12",
    "InvoiceDate": "2009-12-01 07:45:00",
    "Price": "6.95",
    "Customer ID": "13085",
    "Country": "United Kingdom",
}


def chunk(n: int = 3, **overrides: object) -> pd.DataFrame:
    return pd.DataFrame([{**ROW, **overrides}] * n)


@pytest.fixture
def conn():
    with connect(get_settings()) as connection:
        yield connection


@pytest.fixture
def blob(conn):
    """A unique fake file name per test; everything it created is deleted afterwards."""
    name = f"test-{uuid.uuid4().hex[:8]}.csv.gz"
    yield name
    conn.rollback()
    for table in ("raw.transactions", "ops.quarantine", "ops.load_log"):
        conn.execute(f"DELETE FROM {table} WHERE source_blob = %s", (name,))
    conn.commit()


def count_rows(conn, blob: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM raw.transactions WHERE source_blob = %s", (blob,)
    ).fetchone()[0]


@pytest.mark.integration
def test_unchanged_file_is_recognised_as_already_loaded(conn, blob):
    assert not already_loaded(conn, blob, "etag-1")

    load_id = start_load(conn, blob, "etag-1")
    load_file(conn, blob, load_id, iter([split_valid_invalid(chunk())]))

    assert already_loaded(conn, blob, "etag-1")
    assert not already_loaded(conn, blob, "etag-2")  # file changed, so it must reload


@pytest.mark.integration
def test_reloading_a_file_replaces_rows_instead_of_duplicating(conn, blob):
    for etag in ("etag-1", "etag-2"):
        load_id = start_load(conn, blob, etag)
        load_file(conn, blob, load_id, iter([split_valid_invalid(chunk(3))]))

    assert count_rows(conn, blob) == 3


@pytest.mark.integration
def test_failure_midway_leaves_no_partial_file(conn, blob):
    def chunks_then_crash():
        yield split_valid_invalid(chunk(3))
        raise RuntimeError("simulated crash on chunk 2")

    load_id = start_load(conn, blob, "etag-1")
    with pytest.raises(RuntimeError):
        load_file(conn, blob, load_id, chunks_then_crash())
    mark_failed(conn, load_id, "simulated crash")

    assert count_rows(conn, blob) == 0  # chunk 1 was rolled back too
    status = conn.execute(
        "SELECT status FROM ops.load_log WHERE load_id = %s", (load_id,)
    ).fetchone()[0]
    assert status == "failed"


@pytest.mark.integration
def test_bad_rows_are_quarantined_with_a_reason(conn, blob):
    mixed = pd.concat([chunk(2), chunk(1, Quantity="0")], ignore_index=True)

    load_id = start_load(conn, blob, "etag-1")
    result = load_file(conn, blob, load_id, iter([split_valid_invalid(mixed)]))

    assert (result.rows_loaded, result.rows_quarantined) == (2, 1)
    reason = conn.execute(
        "SELECT reason FROM ops.quarantine WHERE source_blob = %s", (blob,)
    ).fetchone()[0]
    assert "quantity" in reason
