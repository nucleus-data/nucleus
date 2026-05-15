-- Silver: revenue per SKU, ranked descending.
-- Joins bronze.orders against bronze.products to surface category metadata.

SELECT
    p.product_id,
    p.name AS product_name,
    p.category,
    cast(sum(o.amount_cents) / 100.0 AS DOUBLE) AS revenue_usd,
    cast(sum(o.quantity) AS BIGINT) AS units_sold,
    cast(count(DISTINCT o.customer_id) AS BIGINT) AS unique_buyers
FROM {{ ref('bronze.products') }} AS p
INNER JOIN {{ ref('bronze.orders') }} AS o
    ON o.product_id = p.product_id
    AND o.status IN ('completed', 'shipped')
GROUP BY p.product_id, p.name, p.category
ORDER BY revenue_usd DESC
