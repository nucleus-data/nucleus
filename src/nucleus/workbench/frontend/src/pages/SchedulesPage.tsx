/**
 * SchedulesPage — /schedules route.
 *
 * Lists registered schedules (assets with a cron expression) and previews
 * the next N run times.
 *
 * Data source: GET /api/schedules (wraps nucleus.coordination.schedules).
 *
 * Per ADR-016 §3 — Fork B layout spec.
 * ADR-017 — Schedule exposure v0.1.
 * nucleus_architecture_v4.1.md §8.1 — Layer 4 Experience.
 *
 * # Stability: Internal @ v0.2
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Clock, ChevronDown, ChevronRight, RefreshCw, Loader2 } from 'lucide-react';
import { fetchSchedules } from '../lib/api';
import TopNav from '../components/TopNav';
import type { ScheduleDTO } from '../types';

function formatNextRun(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const delta = Math.max(0, Math.floor((d.getTime() - now) / 1000));
  if (delta < 60) return `in ${delta}s`;
  if (delta < 3600) return `in ${Math.floor(delta / 60)}m`;
  if (delta < 86400) return `in ${Math.floor(delta / 3600)}h ${Math.floor((delta % 3600) / 60)}m`;
  return d.toLocaleString();
}

function ScheduleCard({ schedule }: { schedule: ScheduleDTO }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      {/* Header row */}
      <button
        onClick={() => setExpanded((e) => !e)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '16px 20px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        aria-expanded={expanded}
      >
        <Clock size={15} style={{ color: 'var(--primary)', flexShrink: 0 }} />
        <span
          className="font-mono"
          style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', flex: 1 }}
        >
          {schedule.asset_key}
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: 12,
            color: 'var(--muted)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '2px 8px',
            flexShrink: 0,
          }}
        >
          {schedule.cron_expression}
        </span>
        {schedule.next_runs.length > 0 && (
          <span style={{ fontSize: 12, color: 'var(--success)', fontWeight: 500, flexShrink: 0 }}>
            {formatNextRun(schedule.next_runs[0])}
          </span>
        )}
        {expanded ? (
          <ChevronDown size={14} style={{ color: 'var(--muted)', flexShrink: 0 }} />
        ) : (
          <ChevronRight size={14} style={{ color: 'var(--muted)', flexShrink: 0 }} />
        )}
      </button>

      {/* Expanded: next run preview */}
      {expanded && (
        <div
          style={{
            borderTop: '1px solid var(--border)',
            padding: '14px 20px 14px 48px',
            background: 'var(--surface)',
          }}
        >
          {schedule.description && (
            <p style={{ fontSize: 13, color: 'var(--muted)', margin: '0 0 10px' }}>
              {schedule.description}
            </p>
          )}

          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Next runs
          </p>

          {schedule.next_runs.length === 0 ? (
            <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>No upcoming runs.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {schedule.next_runs.map((iso, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
                  <span className="font-mono" style={{ color: 'var(--text)', minWidth: 180 }}>
                    {new Date(iso).toLocaleString()}
                  </span>
                  <span style={{ color: 'var(--muted)' }}>{formatNextRun(iso)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SchedulesPage() {
  const { data: schedules = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['schedules'],
    queryFn: fetchSchedules,
    staleTime: 60_000,
  });

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ padding: '28px 40px', maxWidth: 860, width: '100%', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0, letterSpacing: '-0.03em' }}>
            Schedules
          </h1>
          {isLoading && <Loader2 size={16} className="spin" style={{ color: 'var(--muted)' }} />}
          <span style={{ fontSize: 13, color: 'var(--muted)', marginLeft: 4 }}>
            {!isLoading && `${schedules.length} scheduled asset${schedules.length !== 1 ? 's' : ''}`}
          </span>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => void refetch()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '6px 12px',
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'transparent',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: 500,
            }}
            aria-label="Refresh schedules"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>

        {/* Error */}
        {isError && (
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              border: '1px solid var(--error)',
              background: 'rgba(239,68,68,0.06)',
              color: 'var(--error)',
              fontSize: 13,
              marginBottom: 20,
            }}
          >
            Failed to load schedules.
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && schedules.length === 0 && (
          <div
            className="card"
            style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}
          >
            <Clock size={32} style={{ opacity: 0.3, margin: '0 auto 12px', display: 'block' }} />
            <p style={{ fontSize: 14, fontWeight: 600, margin: '0 0 6px', color: 'var(--text)' }}>
              No scheduled assets
            </p>
            <p style={{ fontSize: 13, margin: 0 }}>
              Add{' '}
              <code
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  background: 'var(--surface)',
                  padding: '1px 5px',
                  borderRadius: 3,
                }}
              >
                schedule=&quot;0 * * * *&quot;
              </code>{' '}
              to a{' '}
              <code
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  background: 'var(--surface)',
                  padding: '1px 5px',
                  borderRadius: 3,
                }}
              >
                @nucleus.asset
              </code>{' '}
              decorator to see it here.
            </p>
          </div>
        )}

        {/* Schedule cards */}
        {!isLoading && schedules.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {schedules.map((s) => (
              <ScheduleCard key={s.asset_key} schedule={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
