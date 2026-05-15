-- Gold: weekly revenue summary + the top 20 SKUs.
-- Materializes a single tabular asset combining headline KPIs (left side)
-- with the leaderboard (right side, padded NULL when no SKU lines up).
-- A real BI dashboard would unpack these into two charts; the demo keeps
-- everything in one asset so a single `nucleus query` shows the result.

WITH weekly AS (
    SELECT
        date_trunc('week', day) AS iso_week_start,
        cast(sum(gross_revenue_usd) AS DOUBLE) AS weekly_revenue_usd,
        cast(sum(order_count) AS BIGINT) AS weekly_orders,
        cast(sum(unique_customers) AS BIGINT) AS weekly_unique_customers
    FROM {{ ref('silver.daily_revenue') }}
    GROUP BY 1
),
ranked_products AS (
    SELECT
        product_id,
        product_name,
        category,
        revenue_usd,
        units_sold,
        row_number() OVER (ORDER BY revenue_usd DESC) AS rank
    FROM {{ ref('silver.top_products') }}
)
SELECT
    w.iso_week_start,
    w.weekly_revenue_usd,
    w.weekly_orders,
    w.weekly_unique_customers,
    p.rank AS top_product_rank,
    p.product_id AS top_product_id,
    p.product_name AS top_product_name,
    p.category AS top_product_category,
    p.revenue_usd AS top_product_revenue_usd
FROM weekly AS w
LEFT JOIN ranked_products AS p
    ON p.rank <= 20
ORDER BY w.iso_week_start, p.rank
