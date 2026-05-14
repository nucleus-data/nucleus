-- Sample orders + customers for examples/01-ecommerce-elt
-- Loaded automatically on first Postgres container start via docker-entrypoint-initdb.d

CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    order_date DATE NOT NULL,
    channel TEXT NOT NULL DEFAULT 'web'
);

CREATE TABLE IF NOT EXISTS public.customers (
    customer_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    signup_ts TIMESTAMP NOT NULL
);

INSERT INTO public.customers (customer_id, email, signup_ts) VALUES
    ('c1', 'ada@example.com', '2026-01-10 09:00:00'),
    ('c2', 'bob@example.com', '2026-02-01 11:30:00'),
    ('c3', 'cho@example.com', '2026-03-15 08:45:00')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO public.orders (order_id, customer_id, amount_cents, order_date, channel) VALUES
    ('o100', 'c1', 4999, '2026-05-01', 'web'),
    ('o101', 'c1', 1200, '2026-05-02', 'web'),
    ('o102', 'c2', 8900, '2026-05-02', 'mobile'),
    ('TEST-001', 'c3', 100, '2026-05-03', 'qa'),
    ('o103', 'c3', 4500, '2026-05-04', 'web')
ON CONFLICT (order_id) DO NOTHING;
