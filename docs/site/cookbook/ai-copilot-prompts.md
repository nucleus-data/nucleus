---
title: AI Copilot Prompts
description: Effective prompts for nucleus chat — getting the most out of the AI Copilot.
---

# AI Copilot Prompts

The Nucleus AI Copilot (`nucleus chat`) works best with specific, context-rich prompts. It automatically injects your asset graph, schema, and recent errors — you don't need to provide those manually.

## Error diagnosis

```bash
# Most effective: paste the error code
nucleus chat "I got NE1002 on mart.daily_revenue. What does it mean and how do I fix it?"

# With context
nucleus chat "Why is analytics.daily_revenue failing? The error says NE1001 but the DB is running."
```

## Asset authoring

```bash
# Scaffold a new asset
nucleus chat "Write a @nucleus.asset that computes 7-day rolling average revenue from analytics.daily_revenue"

# SQL transform
nucleus chat "Write a @nucleus.sql_asset for mart.customer_ltv that computes lifetime value from staging.orders and dim.customers"

# Add a check
nucleus chat "Write a @nucleus.check for mart.daily_revenue that alerts if revenue drops more than 30% day-over-day"
```

## Asset graph exploration

```bash
# Dependency exploration
nucleus chat "Which assets in my project depend on raw.orders?"

# Impact analysis
nucleus chat "If I change the schema of raw.orders to remove the currency column, which downstream assets will break?"

# Lineage explanation
nucleus chat "Trace the data lineage from Postgres public.orders to mart.daily_revenue"
```

## SQL debugging

```bash
# Query help
nucleus chat "My DuckDB query is returning duplicates even after GROUP BY. What could cause this?"

# Optimization
nucleus chat "This SQL is slow: SELECT * FROM {{ ref('raw.events') }} WHERE date = TODAY(). How can I optimize it?"
```

## Schema and contract help

```bash
# Contract authoring
nucleus chat "Write a @nucleus.contract for mart.daily_revenue with not-null, positive revenue, and unique order_date constraints"

# Schema evolution
nucleus chat "I need to add a region column to staging.orders. What Iceberg evolution rules apply and how do I update the contract?"
```

## Prompt tips

| Do | Don't |
|----|-------|
| Reference asset keys by their exact name | Give vague descriptions like "my revenue table" |
| Include the NE error code when debugging | Paste raw Python tracebacks (Copilot ignores internal frames) |
| Ask one focused question per prompt | Ask multi-part questions in one prompt |
| Be specific about the mode (overwrite/append/merge) when asking about ingestion | Assume the Copilot knows your exact source schema |

## Provider considerations

| Provider | Privacy | Cost | Offline |
|----------|---------|------|---------|
| Anthropic (default) | Data sent to Anthropic's API | ~$0.003-0.01/query | No |
| OpenAI | Data sent to OpenAI's API | ~$0.002-0.008/query | No |
| Ollama | Local — no data leaves your machine | Free | Yes |

For sensitive data environments, use Ollama with a local model like `llama3` or `codellama`.
