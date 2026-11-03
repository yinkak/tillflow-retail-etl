-- Silver: raw transactions deduplicated, cleaned and classified.
-- Rebuilt from scratch on every run, so it always reflects raw exactly.
DROP TABLE IF EXISTS staging.transactions;

CREATE TABLE staging.transactions AS
WITH numbered AS (
    SELECT
        r.*,
        -- Number identical rows 1, 2, 3...; keeping only #1 removes exact duplicates.
        ROW_NUMBER() OVER (
            PARTITION BY invoice, stock_code, description, quantity,
                         invoice_date, price, customer_id, country
            ORDER BY load_id
        ) AS copy_number
    FROM raw.transactions AS r
)
SELECT
    invoice,
    stock_code,
    TRIM(description) AS description,
    quantity,
    invoice_date,
    price,
    customer_id,
    CASE country
        WHEN 'EIRE' THEN 'Ireland'
        WHEN 'RSA'  THEN 'South Africa'
        ELSE country
    END AS country,
    quantity * price AS line_revenue,

    -- Classification flags (Phase 4 profiling findings)
    invoice LIKE 'C%'                               AS is_cancellation,
    invoice LIKE 'A%'                               AS is_adjustment,
    quantity < 0 AND invoice NOT LIKE 'C%'          AS is_stock_writeoff,
    stock_code !~ '^[0-9]{5}[A-Za-z]*$'             AS is_non_product,

    -- Convenience flag: a genuine product sale to a customer
    invoice !~ '^[CA]'
        AND quantity > 0
        AND price > 0
        AND stock_code ~ '^[0-9]{5}[A-Za-z]*$'      AS is_product_sale,

    source_blob,
    load_id
FROM numbered
WHERE copy_number = 1;
