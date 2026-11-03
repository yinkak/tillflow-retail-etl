-- Gold: one row per customer, scored on Recency, Frequency and Monetary value (1 = low, 5 = high).
DROP TABLE IF EXISTS marts.customer_rfm;

CREATE TABLE marts.customer_rfm AS
WITH sales AS (
    SELECT customer_id, invoice, invoice_date, line_revenue
    FROM staging.transactions
    WHERE is_product_sale
      AND customer_id IS NOT NULL
),
as_of AS (
    -- Measure recency from the day after the last transaction in the data, not from today
    SELECT MAX(invoice_date)::date + 1 AS as_of_date
    FROM staging.transactions
),
per_customer AS (
    SELECT
        customer_id,
        MAX(invoice_date)::date      AS last_purchase_date,
        COUNT(DISTINCT invoice)      AS frequency,
        ROUND(SUM(line_revenue), 2)  AS monetary
    FROM sales
    GROUP BY customer_id
),
scored AS (
    SELECT
        p.customer_id,
        a.as_of_date - p.last_purchase_date AS recency_days,
        p.frequency,
        p.monetary,
        NTILE(5) OVER (ORDER BY a.as_of_date - p.last_purchase_date DESC) AS r_score,
        NTILE(5) OVER (ORDER BY p.frequency)                              AS f_score,
        NTILE(5) OVER (ORDER BY p.monetary)                               AS m_score
    FROM per_customer AS p
    CROSS JOIN as_of AS a
)
SELECT
    *,
    r_score::text || f_score::text || m_score::text AS rfm_code
FROM scored;
