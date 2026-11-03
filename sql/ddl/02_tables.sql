-- One row per attempt to load a file. The ETag tells us whether we've loaded this exact file before.
CREATE TABLE IF NOT EXISTS ops.load_log (
    load_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_blob      TEXT        NOT NULL,
    blob_etag        TEXT        NOT NULL,
    status           TEXT        NOT NULL
                     CHECK (status IN ('running', 'success', 'failed', 'skipped')),
    rows_read        INTEGER,
    rows_loaded      INTEGER,
    rows_quarantined INTEGER,
    error_message    TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ
);

-- Bronze: valid rows exactly as received (typed), plus lineage back to the file and load.
CREATE TABLE IF NOT EXISTS raw.transactions (
    invoice       TEXT      NOT NULL,
    stock_code    TEXT      NOT NULL,
    description   TEXT,
    quantity      INTEGER   NOT NULL,
    invoice_date  TIMESTAMP NOT NULL,
    price         NUMERIC   NOT NULL,
    customer_id   TEXT,
    country       TEXT      NOT NULL,
    source_blob   TEXT      NOT NULL,
    load_id       BIGINT    NOT NULL REFERENCES ops.load_log (load_id)
);

CREATE INDEX IF NOT EXISTS ix_raw_transactions_source_blob
    ON raw.transactions (source_blob);

-- Rows that failed validation, kept with their original values and the reason.
CREATE TABLE IF NOT EXISTS ops.quarantine (
    quarantine_id  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_id        BIGINT      NOT NULL REFERENCES ops.load_log (load_id),
    source_blob    TEXT        NOT NULL,
    raw_values     JSONB       NOT NULL,
    reason         TEXT        NOT NULL,
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
