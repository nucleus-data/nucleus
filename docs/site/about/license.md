---
title: License
description: Nucleus is licensed under Apache License 2.0.
---

# License

Nucleus is licensed under the **Apache License 2.0**.

```
Copyright 2026 Nucleus Team

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Full license text: [`LICENSE`](https://github.com/nucleus-data/nucleus/blob/main/LICENSE)

## Why Apache-2.0?

Apache-2.0 is the right license for a data infrastructure project because:

- It is compatible with the licenses of all wrapped components (DuckDB MIT, Polars MIT, Dagster Apache-2.0, pyiceberg Apache-2.0)
- It allows commercial use without restriction
- It is familiar to enterprise legal teams
- It is the same license as Apache Iceberg, Arrow, and Parquet — the immortal substrate

Per [ADR-007](../governance/architecture-decisions.md), Nucleus's dependency license tier policy enforces Apache-2.0 / MIT / BSD for all Tier 0/1 dependencies.
