-- Gold: monthly product-sales revenue with running total and month-over-month change.
DROP TABLE IF EXISTS marts.monthly_revenue;

CREATE TABLE marts.monthly_revenue AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::date AS month,
        ROUND(SUM(line_revenue), 2)             AS revenue,
        COUNT(DISTINCT invoice)                 AS orders,
        COUNT(DISTINCT customer_id)             AS known_customers
    FROM staging.transactions
    WHERE is_product_sale
    GROUP BY 1
),
last_month AS (
    SELECT DATE_TRUNC('month', MAX(invoice_date))::date AS month
    FROM staging.transactions
)
SELECT
    m.month,
    m.revenue,
    m.orders,
    m.known_customers,
    SUM(m.revenue) OVER (ORDER BY m.month) AS running_revenue,
    ROUND(
        100.0 * (m.revenue - LAG(m.revenue) OVER (ORDER BY m.month))
        / NULLIF(LAG(m.revenue) OVER (ORDER BY m.month), 0),
        1
    ) AS mom_change_pct,
    m.month = l.month AS is_partial_month
FROM monthly AS m
CROSS JOIN last_month AS l;
