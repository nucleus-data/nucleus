/**
 * RecentRunsCard — left column card on the Dashboard Editorial Hero.
 *
 * Shows recent materialization runs with status dot + asset key
 * (in monospace) + duration + relative time.
 *
 * "View all →" link navigates to /runs.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 */

import { Link } from 'react-router-dom';
import type { RunDTO } from '../types';

interface Props {
  runs: RunDTO[];
  loading?: boolean;
}

function relativeTime(epochSeconds: number): string {
  const delta = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

function statusColor(status: string): string {
  switch (status) {
    case 'success': return 'var(--success)';
    case 'failure': return 'var(--error)';
    case 'running': return 'var(--warning)';
    default:        return 'var(--skip)';
  }
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function RunSkeleton() {
  return (
    <>
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="run-row" style={{ cursor: 'default' }}>
          <div className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }} />
          <div className="skeleton" style={{ width: '55%', height: 13 }} />
          <div className="skeleton" style={{ width: 30, height: 12, marginLeft: 'auto' }} />
          <div className="skeleton" style={{ width: 45, height: 12 }} />
        </div>
      ))}
    </>
  );
}

export default function RecentRunsCard({ runs, loading = false }: Props) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 300 }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '16px 18px 12px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.01em' }}>
          Recent runs
        </span>
        <Link
          to="/runs"
          style={{
            marginLeft: 'auto',
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--primary)',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 2,
          }}
        >
          View all →
        </Link>
      </div>

      {/* Run list */}
      <div style={{ padding: '4px 18px', flex: 1, overflow: 'auto' }}>
        {loading ? (
          <RunSkeleton />
        ) : runs.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              minHeight: 160,
              color: 'var(--muted)',
              gap: 8,
            }}
          >
            <span style={{ fontSize: 28, opacity: 0.3 }}>▶</span>
            <p style={{ fontSize: 12, margin: 0, textAlign: 'center' }}>
              No runs yet —{' '}
              <code style={{ fontSize: 11, background: 'var(--surface)', padding: '1px 4px', borderRadius: 3 }}>
                nucleus run &lt;asset&gt;
              </code>{' '}
              to start
            </p>
          </div>
        ) : (
          runs.slice(0, 8).map((r) => (
            <Link
              key={r.run_id}
              to={`/runs/${r.run_id}`}
              className="run-row"
              style={{ textDecoration: 'none', color: 'inherit', padding: '7px 4px' }}
            >
              {/* Status dot */}
              <div
                className="status-dot"
                style={{ background: statusColor(r.status) }}
                title={r.status}
              />

              {/* Asset key in monospace */}
              <span
                className="font-mono"
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--text)',
                  flex: 1,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {r.asset_key}
              </span>

              {/* Duration */}
              <span style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>
                {formatDuration(r.duration_ms)}
              </span>

              {/* Relative time */}
              <span style={{ fontSize: 11, color: 'var(--subtle)', flexShrink: 0, minWidth: 52, textAlign: 'right' }}>
                {relativeTime(r.started_at)}
              </span>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
