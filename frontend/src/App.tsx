import { useEffect, useState } from "react";

// Docs: https://react.dev/reference/react/useState
// Docs: https://react.dev/reference/react/useEffect
// Docs: https://developer.mozilla.org/en-US/docs/Web/API/fetch

type VersionPayload = Record<string, string>;

export default function App() {
  const [payload, setPayload] = useState<VersionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/version")
      .then((r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`);
        }
        return r.json() as Promise<VersionPayload>;
      })
      .then(setPayload)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Request failed"),
      );
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <h1 className="text-3xl font-semibold tracking-tight mb-2">
        Nucleus Workbench
      </h1>
      <p className="text-sm text-amber-300/90 mb-6 rounded border border-amber-400/40 bg-amber-950/40 px-3 py-2 inline-block">
        v0.2 scaffold — full UI shipping Mo 8–14 per ADR-016
      </p>
      <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 max-w-xl">
        <h2 className="text-sm uppercase tracking-wide text-slate-400 mb-2">
          GET /api/version
        </h2>
        {error ? (
          <p className="text-red-400 text-sm">Error: {error}</p>
        ) : payload ? (
          <pre className="text-xs text-slate-200 whitespace-pre-wrap break-all">
            {JSON.stringify(payload, null, 2)}
          </pre>
        ) : (
          <p className="text-slate-500 text-sm">Loading…</p>
        )}
      </section>
    </main>
  );
}
