-- Silver: daily revenue from completed orders.
-- Reads bronze.orders via ctx.sql {{ ref() }} resolution
-- (per docs/specs/nucleus_architecture_v4.1.md §5.6.0 native ctx.sql Jinja resolver).

SELECT
    cast(order_ts AS DATE) AS day,
    channel,
    cast(sum(amount_cents) AS BIGINT) AS gross_revenue_cents,
    cast(sum(amount_cents) / 100.0 AS DOUBLE) AS gross_revenue_usd,
    cast(count(*) AS BIGINT) AS order_count,
    cast(count(DISTINCT customer_id) AS BIGINT) AS unique_customers
FROM {{ ref('bronze.orders') }}
WHERE status IN ('completed', 'shipped')
GROUP BY 1, 2
ORDER BY 1, 2
