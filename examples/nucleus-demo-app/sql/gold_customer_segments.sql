-- Gold: cohort segments by signup quarter and lifetime-value bucket.
-- Drives a "who are our best customers?" view in the Workbench.

WITH bucketed AS (
    SELECT
        customer_id,
        country,
        signup_ts,
        cast(date_trunc('quarter', signup_ts) AS DATE) AS signup_quarter,
        coalesce(lifetime_revenue_usd, 0.0) AS lifetime_revenue_usd,
        order_count,
        CASE
            WHEN coalesce(lifetime_revenue_usd, 0.0) >= 500 THEN 'whale'
            WHEN coalesce(lifetime_revenue_usd, 0.0) >= 200 THEN 'core'
            WHEN coalesce(lifetime_revenue_usd, 0.0) >= 50  THEN 'casual'
            WHEN order_count > 0                            THEN 'trial'
            ELSE 'never_purchased'
        END AS segment
    FROM {{ ref('silver.customer_ltv') }}
)
SELECT
    signup_quarter,
    country,
    segment,
    cast(count(*) AS BIGINT) AS customer_count,
    cast(sum(lifetime_revenue_usd) AS DOUBLE) AS segment_revenue_usd,
    cast(avg(lifetime_revenue_usd) AS DOUBLE) AS avg_ltv_usd
FROM bucketed
GROUP BY signup_quarter, country, segment
ORDER BY signup_quarter, country, segment
