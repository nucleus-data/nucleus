---
title: Errors API
description: Auto-generated API reference for nucleus.errors — all NucleusError subclasses.
---

# `nucleus.errors` — Error Types

::: nucleus.errors
    options:
      show_root_heading: true
      show_source: false
      members_order: source
      filters:
        - "!^_"

---

## Quick reference

All errors are subclasses of `NucleusError` and carry three fields:

```python
error.user_message    # what went wrong, in user language
error.fix_hint        # concrete suggestion to fix it
error.docs_url        # https://nucleus.dev/errors/<slug>
```

Plus optional fields:

```python
error.asset           # the asset involved (if any)
error.cause           # the original translated exception
error.error_code      # "NE1002" etc — permanent, never recycled
```

See [Errors index](../errors/index.md) for the full NE-code table.
