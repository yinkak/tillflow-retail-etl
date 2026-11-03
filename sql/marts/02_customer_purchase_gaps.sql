-- Gold: purchase rhythm per customer, based on days between purchase days.
DROP TABLE IF EXISTS marts.customer_purchase_gaps;

CREATE TABLE marts.customer_purchase_gaps AS
WITH purchase_days AS (
    -- One row per customer per day: several orders on one day count as one visit
    SELECT DISTINCT customer_id, invoice_date::date AS purchase_date
    FROM staging.transactions
    WHERE is_product_sale
      AND customer_id IS NOT NULL
),
gaps AS (
    SELECT
        customer_id,
        purchase_date,
        purchase_date - LAG(purchase_date) OVER (
            PARTITION BY customer_id ORDER BY purchase_date
        ) AS gap_days
    FROM purchase_days
)
SELECT
    customer_id,
    COUNT(*)                      AS purchase_days,
    MIN(purchase_date)            AS first_purchase,
    MAX(purchase_date)            AS last_purchase,
    ROUND(AVG(gap_days), 1)       AS mean_gap_days,
    ROUND(STDDEV_SAMP(gap_days), 1) AS sd_gap_days
FROM gaps
GROUP BY customer_id;
