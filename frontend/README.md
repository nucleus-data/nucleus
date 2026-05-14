# Nucleus Workbench — frontend scaffold

Vite + React 18 + TypeScript shell for the v0.2 Workbench (Layer 4 Experience).

## Setup

```bash
cd frontend
npm install
npm run dev
```

- Dev server: [http://localhost:5173](http://localhost:5173) — proxies `/api` to the FastAPI backend at [http://localhost:8765](http://localhost:8765).
- Production-style bundle: `npm run build` writes outputs to `../src/nucleus/workbench/static` (see `vite.config.ts`).

## References

- Decision record: [`docs/decisions/ADR-016-workbench-mvp.md`](../docs/decisions/ADR-016-workbench-mvp.md)
- Companion research: [`docs/research/workbench.md`](../docs/research/workbench.md)

## Stability

This tree is a **v0.2 scaffold**; HTTP and UI contracts are **Internal** tier and
may change before v1.0 per ADR-005.
