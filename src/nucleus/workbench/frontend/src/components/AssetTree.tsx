/**
 * AssetTree — left-panel tree showing registered assets grouped by schema.
 *
 * Clicking an asset sets selectedAssetKey in the UI store so AssetDAG and
 * AssetDetailsPanel can respond.
 */

import { Database, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import type { AssetDTO } from '../types';
import { useUIStore } from '../App';

interface Props {
  assets: AssetDTO[];
}

export default function AssetTree({ assets }: Props) {
  const { selectedAssetKey, setSelectedAsset } = useUIStore();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Group assets by schema (first part of key, e.g. "raw" from "raw.orders").
  const groups = assets.reduce<Record<string, AssetDTO[]>>((acc, a) => {
    const schema = a.key.split('.')[0] ?? 'default';
    (acc[schema] ??= []).push(a);
    return acc;
  }, {});

  if (assets.length === 0) {
    return (
      <div style={{ padding: 12, color: 'var(--muted)', fontSize: 12 }}>
        No assets registered.
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 0' }}>
      {Object.entries(groups).sort().map(([schema, items]) => {
        const isCollapsed = collapsed.has(schema);
        return (
          <div key={schema}>
            {/* Schema group header */}
            <button
              onClick={() =>
                setCollapsed((prev) => {
                  const next = new Set(prev);
                  if (next.has(schema)) next.delete(schema);
                  else next.add(schema);
                  return next;
                })
              }
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 12px', border: 'none', background: 'transparent',
                color: 'var(--muted)', cursor: 'pointer', fontSize: 11,
                fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
              }}
            >
              <ChevronRight
                size={12}
                style={{ transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)', transition: 'transform 0.15s' }}
              />
              {schema}
            </button>

            {/* Asset items */}
            {!isCollapsed &&
              items.map((a) => {
                const isSelected = a.key === selectedAssetKey;
                return (
                  <button
                    key={a.key}
                    onClick={() => setSelectedAsset(isSelected ? null : a.key)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: 6,
                      padding: '5px 12px 5px 24px', border: 'none',
                      background: isSelected ? 'var(--primary)' : 'transparent',
                      color: isSelected ? '#fff' : 'var(--text)',
                      cursor: 'pointer', fontSize: 12, textAlign: 'left',
                    }}
                  >
                    <Database size={11} style={{ flexShrink: 0, opacity: 0.7 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.key.split('.').slice(1).join('.')}
                    </span>
                    {a.schedule && (
                      <span
                        style={{
                          marginLeft: 'auto', fontSize: 9,
                          background: isSelected ? 'rgba(255,255,255,0.2)' : 'var(--success)',
                          color: isSelected ? '#fff' : '#fff', borderRadius: 9999, padding: '1px 5px',
                          flexShrink: 0,
                        }}
                      >
                        ⏱
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        );
      })}
    </div>
  );
}
