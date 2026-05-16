/**
 * AssetDetailPage — /assets/:key drilldown route.
 *
 * Shows: schema, snapshot history, lineage (deps/dependents), checks,
 * and a "Run" trigger button.
 *
 * Per ADR-016 §3 — Fork B layout spec.
 * docs/specs/nucleus_architecture_v4.1.md §8.1 — Layer 4 Experience.
 *
 * # Stability: Internal @ v0.2
 */

import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  ArrowLeft, Database, CheckCircle, AlertTriangle,
  Play, Loader2, Clock, GitBranch, RefreshCw,
} from 'lucide-react';
import { fetchAsset, fetchRuns, triggerRun, ApiError } from '../lib/api';
import TopNav from '../components/TopNav';

export default function AssetDetailPage() {
  const { key = '' } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const [runError, setRunError] = useState<string | null>(null);
  const [triggerSuccess, setTriggerSuccess] = useState(false);

  const decodedKey = decodeURIComponent(key);

  const { data: asset, isLoading, isError } = useQuery({
    queryKey: ['asset', decodedKey],
    queryFn: () => fetchAsset(decodedKey),
    staleTime: 30_000,
    enabled: !!decodedKey,
  });

  const { data: runs = [] } = useQuery({
    queryKey: ['runs'],
    queryFn: () => fetchRuns(20),
    staleTime: 15_000,
  });

  const assetRuns = runs.filter((r) => r.asset_key === decodedKey).slice(0, 5);

  const triggerMutation = useMutation({
    mutationFn: () => triggerRun({ asset_key: decodedKey }),
    onSuccess: () => {
      setTriggerSuccess(true);
      setRunError(null);
      setTimeout(() => setTriggerSuccess(false), 3000);
    },
    onError: (e) => {
      setRunError(e instanceof ApiError ? e.message : 'Failed to trigger run.');
    },
  });

  function statusColor(s: string) {
    switch (s) {
      case 'success': return 'var(--success)';
      case 'failure': return 'var(--error)';
      case 'running': return 'var(--warning)';
      default: return 'var(--skip)';
    }
  }

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ padding: '28px 40px', maxWidth: 900, width: '100%', margin: '0 auto' }}>
        {/* Breadcrumb */}
        <button
          onClick={() => navigate('/assets')}
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
          Back to Assets
        </button>

        {/* Loading state */}
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--muted)', fontSize: 13 }}>
            <Loader2 size={16} className="spin" />
            Loading asset…
          </div>
        )}

        {/* Error state */}
        {isError && (
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
            Asset &quot;{decodedKey}&quot; not found. Check that the module defining this asset is imported.
          </div>
        )}

        {asset && (
          <>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 28 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 10,
                  background: 'rgba(42,91,250,0.08)',
                  border: '1px solid rgba(42,91,250,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Database size={22} style={{ color: 'var(--primary)' }} />
              </div>

              <div style={{ flex: 1 }}>
                <h1
                  className="font-mono"
                  style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)', margin: '0 0 4px', letterSpacing: '-0.02em' }}
                >
                  {decodedKey}
                </h1>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {asset.schedule && (
                    <span className="badge badge-success">
                      <Clock size={11} style={{ marginRight: 3 }} />
                      {asset.schedule}
                    </span>
                  )}
                  {asset.has_contract && (
                    <span className="badge badge-purple">Contract</span>
                  )}
                  {asset.compute && (
                    <span className="badge badge-muted">{asset.compute}</span>
                  )}
                </div>
              </div>

              {/* Run trigger */}
              <button
                onClick={() => triggerMutation.mutate()}
                disabled={triggerMutation.isPending}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: triggerSuccess ? 'var(--success)' : 'var(--primary)',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: triggerMutation.isPending ? 'not-allowed' : 'pointer',
                  opacity: triggerMutation.isPending ? 0.7 : 1,
                  transition: 'background 0.2s',
                }}
                aria-label={`Trigger materialization of ${decodedKey}`}
              >
                {triggerMutation.isPending ? (
                  <Loader2 size={14} className="spin" />
                ) : (
                  <Play size={14} />
                )}
                {triggerSuccess ? 'Triggered!' : 'Run'}
              </button>
            </div>

            {/* Run error */}
            {runError && (
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
                {runError}
              </div>
            )}

            {/* Info grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 20,
                marginBottom: 28,
              }}
            >
              {/* Dependencies */}
              <div className="card" style={{ padding: '18px 20px' }}>
                <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Dependencies
                </h2>
                {asset.deps.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--muted)', margin: 0 }}>No dependencies (source asset)</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {asset.deps.map((dep) => (
                      <Link
                        key={dep}
                        to={`/assets/${encodeURIComponent(dep)}`}
                        className="font-mono"
                        style={{
                          fontSize: 13,
                          color: 'var(--primary)',
                          textDecoration: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <GitBranch size={12} style={{ flexShrink: 0 }} />
                        {dep}
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* Checks */}
              <div className="card" style={{ padding: '18px 20px' }}>
                <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Checks
                </h2>
                {asset.checks.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--muted)', margin: 0 }}>No checks defined</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {asset.checks.map((c, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                        {c.severity === 'error' ? (
                          <AlertTriangle size={13} style={{ color: 'var(--warning)', flexShrink: 0 }} />
                        ) : (
                          <CheckCircle size={13} style={{ color: 'var(--success)', flexShrink: 0 }} />
                        )}
                        <span className="font-mono" style={{ color: 'var(--text)' }}>{c.fn_name}</span>
                        <span className={`badge badge-${c.severity === 'error' ? 'error' : 'muted'}`} style={{ marginLeft: 'auto' }}>
                          {c.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Recent run history */}
            <div className="card" style={{ padding: '18px 20px', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
                <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Recent materializations
                </h2>
                <Link to="/runs" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--primary)', textDecoration: 'none' }}>
                  View all →
                </Link>
              </div>

              {assetRuns.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--muted)', margin: 0 }}>
                  No runs recorded — click Run above to materialize.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {assetRuns.map((r) => (
                    <Link
                      key={r.run_id}
                      to={`/runs/${r.run_id}`}
                      className="run-row"
                      style={{ textDecoration: 'none', color: 'inherit', padding: '8px 4px' }}
                    >
                      <div className="status-dot" style={{ background: statusColor(r.status) }} />
                      <span style={{ fontSize: 12, color: 'var(--muted)', flex: 1 }}>
                        {new Date(r.started_at * 1000).toLocaleString()}
                      </span>
                      <span className={`badge badge-${r.status === 'success' ? 'success' : r.status === 'failure' ? 'error' : 'warning'}`}>
                        {r.status}
                      </span>
                      {r.duration_ms != null && (
                        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                          {r.duration_ms < 1000 ? `${r.duration_ms}ms` : `${(r.duration_ms / 1000).toFixed(1)}s`}
                        </span>
                      )}
                      {r.rows_written != null && (
                        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                          {r.rows_written.toLocaleString()} rows
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
