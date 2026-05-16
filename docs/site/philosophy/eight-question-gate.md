---
title: Eight-Question Gate
description: The checklist every new feature must pass before being considered for Nucleus v0.1.
---

# Eight-Question Gate

Before any new feature, component, or abstraction is added to Nucleus, it must pass all eight questions. A "no" or "unclear" on any question means the feature is rejected or deferred.

## The questions

1. **Does it map to one of the five architectural layers?**

   Physics / Engines / Coordination / Intelligence / Experience — each maps to a concrete layer in v4.1 §3.1. Features that don't fit a layer are scope creep.

2. **Does it serve the &lt;30-minute beachhead metric?**

   A 5-engineer startup team, on MacBooks, with Postgres source, builds their first BI-ready Iceberg table from `git clone` in &lt;30 minutes. If the feature doesn't help that goal, it's deferred.

3. **Can we wrap it instead of building it?**

   Per [Wrap, Not Build](wrap-not-build.md) — if an OSS library exists, wrap it. Building is the last resort.

4. **Does it preserve the no-JVM constraint?**

   No Java, Scala, or JVM-based components in the default path. Ever. This is non-negotiable for Constraint #1.

5. **Does it preserve local-identical-to-prod?**

   What runs on a MacBook must behave identically to what runs in production. No "local-only" features that create drift.

6. **Does it stay within the &lt;30K LOC budget?**

   Track against [`docs/internal/budget_history.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/budget_history.md). If a feature would push past the phase ceiling, defer it.

7. **Is it triggered by empirical telemetry, not anxiety?**

   "Users might need X" is not enough. Real usage data, user interviews, or PoC #5 feedback is required for non-trivial features.

8. **Is it required for v0.1 Hello World (Mo 0-4), or can it defer?**

   v0.1 = init/up/down/run/ingest/query/version. Everything else is v0.2/0.3/0.5+. "Nice to have" is not a v0.1 justification.

## Using the gate

Write out your answers before proposing:

```
Feature: [name]
1. Layer: [Physics/Engines/Coordination/Intelligence/Experience]
2. Beachhead: [yes/no/partial — explain]
3. Wrap: [wrap target / builds from scratch — ADR required]
4. No-JVM: [yes/no]
5. Local=Prod: [yes/no]
6. LOC budget: [estimated lines + current budget remaining]
7. Empirical trigger: [user quote / PoC result / telemetry data]
8. v0.1 required: [yes / defer to vX.Y]
```

If any answer is "no" or "unclear" — the feature is deferred. Document the imagined need in [`docs/internal/FOUNDER_ACTION_QUEUE.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/FOUNDER_ACTION_QUEUE.md) for later reconsideration.

## Anti-patterns this prevents

- **Scope creep** — adding v0.3 features in v0.1 because "it's easy"
- **Speculative abstraction** — adding an abstraction "for future use cases"
- **Anxiety-driven features** — building things because they *might* be needed
- **Composability Tax** — maintaining full second implementations of every alternative
