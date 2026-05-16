/**
 * RunDetailPage — /runs/:run_id route.
 *
 * Shows: run metadata + live SSE log stream viewer.
 *
 * Per ADR-016 §3 — Fork B API surface.
 * docs/specs/nucleus_architecture_v4.1.md §8.1 — Layer 4 Experience.
 *
 * # Stability: Internal @ v0.2
 */

import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Terminal } from 'lucide-react';
import { fetchRuns } from '../lib/api';
import TopNav from '../components/TopNav';

function statusColor(s: string) {
  switch (s) {
    case 'success': return 'var(--success)';
    case 'failure': return 'var(--error)';
    case 'running': return 'var(--warning)';
    default: return 'var(--skip)';
  }
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export default function RunDetailPage() {
  const { run_id = '' } = useParams<{ run_id: string }>();
  const navigate = useNavigate();
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logDone, setLogDone] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: () => fetchRuns(200),
    staleTime: 15_000,
  });

  const run = runs.find((r) => r.run_id === run_id) ?? null;

  // SSE log stream
  useEffect(() => {
    if (!run_id) return;
    setLogLines([]);
    setLogDone(false);

    const es = new EventSource(`/api/runs/${run_id}/log`);

    es.onmessage = (event) => {
      if (event.data === '[DONE]') {
        setLogDone(true);
        es.close();
        return;
      }
      try {
        const parsed = JSON.parse(event.data) as { line: string };
        setLogLines((prev) => [...prev, parsed.line]);
        setTimeout(() => {
          logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 50);
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setLogDone(true);
      es.close();
    };

    return () => es.close();
  }, [run_id]);

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ padding: '28px 40px', maxWidth: 900, width: '100%', margin: '0 auto', flex: 1, display: 'flex', flexDirection: 'column' }}>
        <button
          onClick={() => navigate('/runs')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--muted)',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            marginBottom: 20,
          }}
        >
          <ArrowLeft size={14} />
          Back to Runs
        </button>

        {isLoading && !run && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--muted)', fontSize: 13 }}>
            <Loader2 size={16} className="spin" />
            Loading run…
          </div>
        )}

        {!isLoading && !run && (
          <div
            style={{
              padding: 16,
              borderRadius: 8,
              border: '1px solid var(--error)',
              background: 'rgba(239,68,68,0.06)',
              color: 'var(--error)',
              fontSize: 13,
            }}
          >
            Run &quot;{run_id}&quot; not found. It may have been evicted from the in-memory store.
          </div>
        )}

        {run && (
          <>
            {/* Header */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', margin: 0, letterSpacing: '-0.02em' }}>
                  Run Log
                </h1>
                <span
                  className={`badge badge-${run.status === 'success' ? 'success' : run.status === 'failure' ? 'error' : 'warning'}`}
                >
                  {run.status}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13, color: 'var(--muted)' }}>
                <span>
                  Asset:{' '}
                  <span className="font-mono" style={{ color: 'var(--text)' }}>{run.asset_key}</span>
                </span>
                <span>Duration: {formatDuration(run.duration_ms)}</span>
                <span>
                  Started:{' '}
                  {new Date(run.started_at * 1000).toLocaleString()}
                </span>
                {run.rows_written != null && (
                  <span>Rows: {run.rows_written.toLocaleString()}</span>
                )}
                {run.snapshot_id && (
                  <span>
                    Snapshot:{' '}
                    <span className="font-mono" style={{ fontSize: 12 }}>{run.snapshot_id.slice(0, 12)}…</span>
                  </span>
                )}
              </div>
            </div>

            {/* Log viewer */}
            <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border)',
                  flexShrink: 0,
                }}
              >
                <Terminal size={13} style={{ color: 'var(--muted)' }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Output
                </span>
                {!logDone && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--warning)', marginLeft: 'auto' }}>
                    <Loader2 size={11} className="spin" />
                    Streaming…
                  </span>
                )}
                {logDone && (
                  <span style={{ fontSize: 11, color: 'var(--success)', marginLeft: 'auto' }}>
                    Complete
                  </span>
                )}
              </div>

              <div
                style={{
                  flex: 1,
                  overflow: 'auto',
                  padding: '14px 18px',
                  background: '#0A0E1A',
                  minHeight: 240,
                }}
              >
                {logLines.length === 0 && logDone && (
                  <p className="font-mono" style={{ fontSize: 12, color: '#5A6273', margin: 0 }}>
                    (no log output)
                  </p>
                )}
                {logLines.map((line, i) => (
                  <p
                    key={i}
                    className="font-mono"
                    style={{
                      fontSize: 12,
                      color: '#C9D1D9',
                      margin: 0,
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {line}
                  </p>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
