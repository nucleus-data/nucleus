/**
 * AssetsPage — /assets route.
 *
 * Layout (updated for Editorial Hero v0.2):
 *   ┌──────────────────────────────────────────────────────────┐
 *   │  TopNav (solid)                                          │
 *   ├────────────────┬─────────────────────────────────────────┤
 *   │  Asset Tree    │  Asset DAG (React Flow, full mode)      │
 *   │  (left 220px)  │                                         │
 *   └────────────────┴─────────────────────────────────────────┘
 *   └─────────────── Asset Details Panel (bottom, if selected) ─┘
 *
 * Per ADR-016 §3 layout spec.
 */

import { useQuery } from '@tanstack/react-query';
import { Loader2, RefreshCw } from 'lucide-react';
import { fetchAssets } from '../lib/api';
import AssetTree from '../components/AssetTree';
import AssetDAG from '../components/AssetDAG';
import AssetDetailsPanel from '../components/AssetDetailsPanel';
import TopNav from '../components/TopNav';
import { useUIStore } from '../App';

export default function AssetsPage() {
  const { selectedAssetKey } = useUIStore();
  const {
    data: assets = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    staleTime: 30_000,
  });

  const selectedAsset = assets.find((a) => a.key === selectedAssetKey) ?? null;

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Asset tree sidebar */}
        <div
          style={{
            width: 220,
            flexShrink: 0,
            borderRight: '1px solid var(--border)',
            background: 'var(--surface)',
            overflow: 'auto',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '10px 12px',
              borderBottom: '1px solid var(--border)',
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Assets
            {isLoading && <Loader2 size={11} className="spin" style={{ marginLeft: 4 }} />}
            <button
              onClick={() => void refetch()}
              style={{
                marginLeft: 'auto',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: 'var(--muted)',
                padding: 2,
              }}
              title="Refresh assets"
              aria-label="Refresh asset list"
            >
              <RefreshCw size={11} />
            </button>
          </div>

          {isError && (
            <div style={{ padding: 12, fontSize: 12, color: 'var(--error)' }}>
              Failed to load assets.
            </div>
          )}

          <AssetTree assets={assets} />
        </div>

        {/* DAG area */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
          {/* Page header overlay */}
          <div
            style={{
              position: 'absolute',
              top: 12,
              left: 12,
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <h1
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--text)',
                margin: 0,
                background: 'var(--bg)',
                padding: '4px 10px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                boxShadow: 'var(--card-shadow)',
              }}
            >
              Asset Graph
            </h1>
            <span
              style={{
                fontSize: 11,
                color: 'var(--muted)',
                background: 'var(--bg)',
                padding: '4px 8px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                boxShadow: 'var(--card-shadow)',
              }}
            >
              {assets.length} assets
            </span>
          </div>

          <AssetDAG assets={assets} />
        </div>
      </div>

      {/* Detail panel at bottom (when an asset is selected) */}
      {selectedAsset && <AssetDetailsPanel asset={selectedAsset} />}
    </div>
  );
}
