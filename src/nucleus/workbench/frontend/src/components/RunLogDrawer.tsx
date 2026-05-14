/**
 * RunLogDrawer — slide-in drawer that shows log lines for a selected run.
 *
 * Connects to GET /api/runs/{run_id}/log (SSE stream).
 * For completed runs, all lines arrive immediately then the stream closes.
 */

import { useEffect, useRef, useState } from 'react';
import { X, Terminal } from 'lucide-react';

interface Props {
  runId: string | null;
  onClose: () => void;
}

export default function RunLogDrawer({ runId, onClose }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) { setLines([]); setDone(false); return; }
    setLines([]);
    setDone(false);

    // SSE connection.
    // Docs: https://developer.mozilla.org/en-US/docs/Web/API/EventSource
    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/log`);
    source.onmessage = (e: MessageEvent<string>) => {
      if (e.data === '[DONE]') {
        setDone(true);
        source.close();
        return;
      }
      try {
        const parsed = JSON.parse(e.data) as { line?: string };
        if (parsed.line) setLines((prev) => [...prev, parsed.line!]);
      } catch {
        setLines((prev) => [...prev, e.data]);
      }
    };
    source.onerror = () => { setDone(true); source.close(); };
    return () => source.close();
  }, [runId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  if (!runId) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 500,
        display: 'flex', justifyContent: 'flex-end',
        background: 'rgba(0,0,0,0.4)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 560, height: '100%', background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '12px 16px', borderBottom: '1px solid var(--border)',
          }}
        >
          <Terminal size={15} style={{ color: 'var(--primary)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1 }}>
            Run log
          </span>
          <code style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>
            {runId.slice(0, 8)}…
          </code>
          {done && (
            <span
              style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 9999,
                background: 'rgba(52,211,153,.15)', color: 'var(--success)',
                fontWeight: 700,
              }}
            >
              DONE
            </span>
          )}
          <button
            onClick={onClose}
            style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--muted)', padding: 2 }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Log lines */}
        <div
          style={{
            flex: 1, overflow: 'auto', padding: '12px 16px',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace', fontSize: 12,
            lineHeight: 1.6, color: 'var(--text)', background: 'var(--bg)',
          }}
        >
          {lines.length === 0 && !done && (
            <span style={{ color: 'var(--muted)' }}>Connecting…</span>
          )}
          {lines.map((line, i) => (
            <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {line}
            </div>
          ))}
          {lines.length === 0 && done && (
            <span style={{ color: 'var(--muted)' }}>No log lines recorded for this run.</span>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
