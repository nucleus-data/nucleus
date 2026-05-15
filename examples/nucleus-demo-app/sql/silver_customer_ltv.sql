-- Silver: lifetime value per customer.
-- Joins bronze.orders against bronze.customers and excludes refunds/cancels.

SELECT
    c.customer_id,
    c.country,
    c.signup_ts,
    cast(sum(o.amount_cents) / 100.0 AS DOUBLE) AS lifetime_revenue_usd,
    cast(count(o.order_id) AS BIGINT) AS order_count,
    cast(min(o.order_ts) AS TIMESTAMP) AS first_order_ts,
    cast(max(o.order_ts) AS TIMESTAMP) AS last_order_ts
FROM {{ ref('bronze.customers') }} AS c
LEFT JOIN {{ ref('bronze.orders') }} AS o
    ON o.customer_id = c.customer_id
    AND o.status IN ('completed', 'shipped')
GROUP BY c.customer_id, c.country, c.signup_ts
ORDER BY lifetime_revenue_usd DESC NULLS LAST
