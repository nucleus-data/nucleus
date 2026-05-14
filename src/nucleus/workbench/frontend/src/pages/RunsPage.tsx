/**
 * RunsPage — /runs route.
 *
 * Shows recent materialization runs in a sortable table (RunsTable).
 * Clicking a row opens the RunLogDrawer for that run's SSE log stream.
 * Updated for Editorial Hero v0.2: includes TopNav.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, RefreshCw } from 'lucide-react';
import { fetchRuns } from '../lib/api';
import RunsTable from '../components/RunsTable';
import RunLogDrawer from '../components/RunLogDrawer';
import TopNav from '../components/TopNav';

export default function RunsPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: runs = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['runs'],
    queryFn: () => fetchRuns(50),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 28, gap: 16 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', margin: 0, letterSpacing: '-0.02em' }}>
            Recent Runs
          </h1>
          {isLoading && <Loader2 size={14} className="spin" style={{ color: 'var(--muted)' }} />}
          <span style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 4 }}>
            {runs.length > 0 ? `${runs.length} run${runs.length !== 1 ? 's' : ''}` : ''}
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
            aria-label="Refresh runs"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>

        {/* Error state */}
        {isError && (
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              border: '1px solid var(--error)',
              background: 'rgba(239,68,68,0.06)',
              color: 'var(--error)',
              fontSize: 13,
            }}
          >
            Failed to load runs. Is the Workbench server running?
          </div>
        )}

        {/* Table */}
        <div
          className="card"
          style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
        >
          <RunsTable
            runs={runs}
            onSelect={(id) => setSelectedRunId(id === selectedRunId ? null : id)}
            selectedRunId={selectedRunId}
          />
        </div>

        {/* Log drawer */}
        <RunLogDrawer
          runId={selectedRunId}
          onClose={() => setSelectedRunId(null)}
        />
      </div>
    </div>
  );
}
