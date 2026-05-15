# `notebooks/`

Optional ad-hoc analysis on top of the demo warehouse. Marimo notebook
support lands in **v0.3+**; for now `exploration.py` is a thin Python
script that reads the gold assets and prints a summary — runnable today
without Marimo.

```bash
python notebooks/exploration.py
```

When Marimo support ships, the same file becomes a reactive notebook
without rewriting any cells.
