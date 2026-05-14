/**
 * PipelineDAGCard — middle column card on the Dashboard Editorial Hero.
 *
 * Wraps the AssetDAG component in a constrained card with:
 * - "Pipeline DAG" header + "⛶ Fit view" button
 * - Height-constrained React Flow canvas (~320px)
 * - Legend: ● Success ● Warning ● Failed ● Skipped
 *
 * Uses AssetDAG's constrained prop to disable controls clutter in card mode.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 */

import { useCallback } from 'react';
import { Maximize2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { AssetDTO } from '../types';
import AssetDAG from './AssetDAG';

interface Props {
  assets: AssetDTO[];
  loading?: boolean;
}

const LEGEND_ITEMS = [
  { label: 'Success', color: 'var(--success)' },
  { label: 'Warning', color: 'var(--warning)' },
  { label: 'Failed',  color: 'var(--error)' },
  { label: 'Skipped', color: 'var(--skip)' },
];

function DAGSkeleton() {
  return (
    <div
      style={{
        height: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {[80, 120, 80].map((w, i) => (
        <div key={i} style={{ display: 'flex', gap: 40 }}>
          {Array.from({ length: i === 1 ? 2 : 1 }).map((_, j) => (
            <div key={j} className="skeleton" style={{ width: w, height: 36, borderRadius: 8 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function PipelineDAGCard({ assets, loading = false }: Props) {
  const navigate = useNavigate();

  const goToAssets = useCallback(() => {
    navigate('/assets');
  }, [navigate]);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 300, overflow: 'hidden' }}>
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
          Pipeline DAG
        </span>
        <button
          onClick={goToAssets}
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--muted)',
            border: '1px solid var(--border)',
            background: 'transparent',
            borderRadius: 6,
            padding: '3px 8px',
            cursor: 'pointer',
          }}
          aria-label="Fit view — go to full asset graph"
          title="Open full asset graph"
        >
          <Maximize2 size={11} />
          Fit view
        </button>
      </div>

      {/* DAG canvas — constrained height */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {loading ? (
          <DAGSkeleton />
        ) : (
          <AssetDAG assets={assets} constrained />
        )}
      </div>

      {/* Legend */}
      <div
        style={{
          padding: '10px 18px',
          borderTop: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <div className="dag-legend">
          {LEGEND_ITEMS.map(({ label, color }) => (
            <div key={label} className="dag-legend-item">
              <div
                className="status-dot"
                style={{ background: color, width: 7, height: 7 }}
              />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
