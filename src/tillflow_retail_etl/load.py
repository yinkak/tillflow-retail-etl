"""Load: bulk-copy validated rows into Postgres, with a load log that makes reruns safe."""

import json
from collections.abc import Iterator
from dataclasses import dataclass

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from tillflow_retail_etl.config import Settings

RAW_COLUMNS = [
    "invoice",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "price",
    "customer_id",
    "country",
    "source_blob",
    "load_id",
]


@dataclass(frozen=True)
class LoadResult:
    rows_loaded: int
    rows_quarantined: int


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(settings.postgres_dsn)


def already_loaded(conn: psycopg.Connection, source_blob: str, etag: str) -> bool:
    """True if this exact version of the file was loaded successfully before."""
    row = conn.execute(
        "SELECT 1 FROM ops.load_log "
        "WHERE source_blob = %s AND blob_etag = %s AND status = 'success' LIMIT 1",
        (source_blob, etag),
    ).fetchone()
    return row is not None


def record_skip(conn: psycopg.Connection, source_blob: str, etag: str) -> None:
    conn.execute(
        "INSERT INTO ops.load_log (source_blob, blob_etag, status, finished_at) "
        "VALUES (%s, %s, 'skipped', clock_timestamp())",
        (source_blob, etag),
    )
    conn.commit()


def start_load(conn: psycopg.Connection, source_blob: str, etag: str) -> int:
    """Record that a load began. Committed right away so a later failure is still visible."""
    load_id = conn.execute(
        "INSERT INTO ops.load_log (source_blob, blob_etag, status) "
        "VALUES (%s, %s, 'running') RETURNING load_id",
        (source_blob, etag),
    ).fetchone()[0]
    conn.commit()
    return load_id


def mark_failed(conn: psycopg.Connection, load_id: int, error: str) -> None:
    conn.execute(
        "UPDATE ops.load_log SET status = 'failed', error_message = %s, "
        "finished_at = clock_timestamp() WHERE load_id = %s",
        (error[:2000], load_id),
    )
    conn.commit()


def load_file(
    conn: psycopg.Connection,
    source_blob: str,
    load_id: int,
    validated_chunks: Iterator[tuple[pd.DataFrame, pd.DataFrame]],
) -> LoadResult:
    """Replace this file's rows in ONE transaction: every chunk lands, or none do."""
    rows_loaded = rows_quarantined = 0

    with conn.transaction():
        conn.execute("DELETE FROM raw.transactions WHERE source_blob = %s", (source_blob,))
        conn.execute("DELETE FROM ops.quarantine WHERE source_blob = %s", (source_blob,))

        for valid, quarantine in validated_chunks:
            rows_loaded += _copy_valid(conn, valid, source_blob, load_id)
            rows_quarantined += _insert_quarantine(conn, quarantine, source_blob, load_id)

        conn.execute(
            "UPDATE ops.load_log SET status = 'success', rows_read = %s, rows_loaded = %s, "
            "rows_quarantined = %s, finished_at = clock_timestamp() WHERE load_id = %s",
            (rows_loaded + rows_quarantined, rows_loaded, rows_quarantined, load_id),
        )

    return LoadResult(rows_loaded=rows_loaded, rows_quarantined=rows_quarantined)


def _copy_valid(
    conn: psycopg.Connection, valid: pd.DataFrame, source_blob: str, load_id: int
) -> int:
    """Bulk-load a chunk with Postgres COPY, far faster than row-by-row INSERTs."""
    if valid.empty:
        return 0
    frame = valid.assign(source_blob=source_blob, load_id=load_id)[RAW_COLUMNS]
    csv_text = frame.to_csv(index=False, header=False)
    columns = ", ".join(RAW_COLUMNS)
    with conn.cursor() as cur:
        with cur.copy(f"COPY raw.transactions ({columns}) FROM STDIN WITH (FORMAT csv)") as copy:
            copy.write(csv_text)
    return len(frame)


def _insert_quarantine(
    conn: psycopg.Connection, quarantine: pd.DataFrame, source_blob: str, load_id: int
) -> int:
    """Store rejected rows as JSON, exactly as received, with their reason."""
    if quarantine.empty:
        return 0
    records = json.loads(quarantine.drop(columns="reason").to_json(orient="records"))
    params = [
        (load_id, source_blob, Jsonb(record), reason)
        for record, reason in zip(records, quarantine["reason"], strict=True)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO ops.quarantine (load_id, source_blob, raw_values, reason) "
            "VALUES (%s, %s, %s, %s)",
            params,
        )
    return len(params)
