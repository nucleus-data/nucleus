/**
 * AssetDetailsPanel — bottom or right panel showing metadata for
 * the currently-selected asset.
 */

import { X, CheckCircle, Clock, GitBranch } from 'lucide-react';
import type { AssetDTO } from '../types';
import { useUIStore } from '../App';

interface Props {
  asset: AssetDTO;
}

export default function AssetDetailsPanel({ asset }: Props) {
  const { setSelectedAsset } = useUIStore();

  return (
    <div
      style={{
        height: 220,
        flexShrink: 0,
        borderTop: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 16px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flex: 1 }}>
          {asset.key}
        </span>
        {asset.schedule && (
          <span
            style={{
              fontSize: 10,
              background: 'rgba(52,211,153,.12)',
              color: 'var(--success)',
              borderRadius: 9999,
              padding: '2px 8px',
              fontWeight: 600,
            }}
          >
            <Clock size={10} style={{ display: 'inline', marginRight: 3 }} />
            {asset.schedule}
          </span>
        )}
        <button
          onClick={() => setSelectedAsset(null)}
          style={{
            border: 'none', background: 'transparent', cursor: 'pointer',
            color: 'var(--muted)', padding: 2, borderRadius: 4,
          }}
          aria-label="Close detail panel"
        >
          <X size={14} />
        </button>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1, overflow: 'auto', padding: '12px 16px',
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12,
        }}
      >
        {/* Dependencies */}
        <section>
          <h3 style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', margin: '0 0 6px', textTransform: 'uppercase' }}>
            <GitBranch size={10} style={{ display: 'inline', marginRight: 4 }} />
            Dependencies
          </h3>
          {asset.deps.length === 0 ? (
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>None (source asset)</span>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {asset.deps.map((dep) => (
                <span
                  key={dep}
                  style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 4,
                    background: 'var(--border)', color: 'var(--text)',
                  }}
                >
                  {dep}
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Checks */}
        <section>
          <h3 style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', margin: '0 0 6px', textTransform: 'uppercase' }}>
            <CheckCircle size={10} style={{ display: 'inline', marginRight: 4 }} />
            Quality Checks
          </h3>
          {asset.checks.length === 0 ? (
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>None declared</span>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {asset.checks.map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontSize: 9, padding: '1px 5px', borderRadius: 9999, fontWeight: 700,
                      background: c.severity === 'error' ? 'rgba(239,68,68,.12)' : 'rgba(52,211,153,.12)',
                      color: c.severity === 'error' ? 'var(--error)' : 'var(--success)',
                    }}
                  >
                    {c.severity}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace' }}>{c.fn_name}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Contract */}
        <section>
          <h3 style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', margin: '0 0 6px', textTransform: 'uppercase' }}>
            Contract
          </h3>
          <span style={{ fontSize: 12, color: 'var(--text)' }}>
            {asset.has_contract ? 'Declared' : 'None'}
          </span>
        </section>

        {/* Compute */}
        <section>
          <h3 style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', margin: '0 0 6px', textTransform: 'uppercase' }}>
            Compute
          </h3>
          <span style={{ fontSize: 12, color: 'var(--text)' }}>
            {asset.compute ?? 'local (default)'}
          </span>
        </section>
      </div>
    </div>
  );
}
