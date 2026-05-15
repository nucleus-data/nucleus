/**
 * CatalogPage — /catalog route.
 *
 * Paginated table view of all registered assets with filter/search.
 * Links to /assets/:key for drilldown.
 *
 * Data source: GET /api/catalog?q=...&page=N&page_size=M
 *
 * Per ADR-016 §3 — Fork B layout spec.
 * nucleus_architecture_v4.1.md §8.1 — Layer 4 Experience.
 *
 * # Stability: Internal @ v0.2
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Search, ChevronLeft, ChevronRight, Database,
  CheckCircle, GitBranch, Loader2,
} from 'lucide-react';
import { fetchCatalog } from '../lib/api';
import TopNav from '../components/TopNav';
import NamespacePath from '../components/NamespacePath';
import { relativeTime, absoluteTime } from '../lib/relativeTime';

const PAGE_SIZE = 25;

export default function CatalogPage() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [debouncedQ, setDebouncedQ] = useState('');

  // Simple debounce via onChange + timeout
  function handleSearch(q: string) {
    setQuery(q);
    setPage(1);
    clearTimeout((handleSearch as unknown as { _timer?: number })._timer);
    (handleSearch as unknown as { _timer?: number })._timer = window.setTimeout(() => {
      setDebouncedQ(q);
    }, 300);
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['catalog', page, debouncedQ],
    queryFn: () => fetchCatalog(page, PAGE_SIZE, debouncedQ),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}
    >
      <TopNav />

      <div style={{ padding: '28px 40px' }}>
        {/* Header + search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0, letterSpacing: '-0.03em' }}>
            Catalog
          </h1>
          {isLoading && <Loader2 size={16} className="spin" style={{ color: 'var(--muted)' }} />}
          {data && (
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>
              {total} asset{total !== 1 ? 's' : ''}
            </span>
          )}

          <div style={{ flex: 1 }} />

          {/* Search box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 12px',
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: 'var(--surface)',
              width: 260,
            }}
          >
            <Search size={13} style={{ color: 'var(--muted)', flexShrink: 0 }} />
            <input
              type="text"
              value={query}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Filter assets…"
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                background: 'transparent',
                fontSize: 13,
                color: 'var(--text)',
              }}
              aria-label="Search assets"
            />
          </div>
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
            Failed to load catalog.
          </div>
        )}

        {/* Table */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr
                style={{
                  background: 'var(--surface)',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {[
                  'Asset',
                  'Schedule',
                  'Contract',
                  'Checks',
                  'Last materialized',
                  'Dependencies',
                  'Compute',
                ].map((col) => (
                  <th
                    key={col}
                    style={{
                      padding: '10px 16px',
                      textAlign: 'left',
                      fontSize: 11,
                      fontWeight: 700,
                      color: 'var(--muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!isLoading && items.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                    <Database size={24} style={{ opacity: 0.3, display: 'block', margin: '0 auto 8px' }} />
                    {query ? `No assets matching "${query}"` : 'No assets registered'}
                  </td>
                </tr>
              )}

              {items.map((row, i) => (
                <tr
                  key={row.key}
                  style={{
                    borderBottom: i < items.length - 1 ? '1px solid var(--border)' : 'none',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(0,0,0,0.02)';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.background = 'transparent';
                  }}
                >
                  {/* Asset — Rec #5 (2026-05-15): namespace · name chip pair
                      + copy-on-click button. Click the chip text to navigate. */}
                  <td style={{ padding: '10px 16px' }}>
                    <Link
                      to={`/assets/${encodeURIComponent(row.key)}`}
                      aria-label={`Open ${row.key}`}
                      style={{ textDecoration: 'none' }}
                    >
                      <NamespacePath fullKey={row.key} namespace={row.namespace} />
                    </Link>
                  </td>

                  {/* Schedule */}
                  <td style={{ padding: '10px 16px' }}>
                    {row.has_schedule ? (
                      <span className="badge badge-success">Scheduled</span>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--subtle)' }}>—</span>
                    )}
                  </td>

                  {/* Contract */}
                  <td style={{ padding: '10px 16px' }}>
                    {row.has_contract ? (
                      <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--subtle)' }}>—</span>
                    )}
                  </td>

                  {/* Checks */}
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ fontSize: 12, color: row.check_count > 0 ? 'var(--text)' : 'var(--subtle)' }}>
                      {row.check_count > 0 ? row.check_count : '—'}
                    </span>
                  </td>

                  {/* Last materialized — Rec #6 (2026-05-15): relative time
                      from RunLedger.list(asset_key, status="success"). */}
                  <td style={{ padding: '10px 16px' }}>
                    <span
                      title={absoluteTime(row.last_materialized) || undefined}
                      style={{
                        fontSize: 12,
                        color: row.last_materialized ? 'var(--text)' : 'var(--subtle)',
                      }}
                    >
                      {relativeTime(row.last_materialized)}
                    </span>
                  </td>

                  {/* Dependencies */}
                  <td style={{ padding: '10px 16px' }}>
                    <span
                      style={{
                        fontSize: 12,
                        color: 'var(--muted)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {row.dep_count > 0 && <GitBranch size={11} />}
                      {row.dep_count > 0 ? row.dep_count : '—'}
                    </span>
                  </td>

                  {/* Compute */}
                  <td style={{ padding: '10px 16px' }}>
                    <span className="font-mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {row.compute ?? 'default'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              marginTop: 20,
            }}
          >
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '6px 12px',
                borderRadius: 7,
                border: '1px solid var(--border)',
                background: 'transparent',
                color: page <= 1 ? 'var(--subtle)' : 'var(--text)',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
                fontSize: 12,
              }}
              aria-label="Previous page"
            >
              <ChevronLeft size={13} />
              Prev
            </button>

            <span style={{ fontSize: 13, color: 'var(--muted)' }}>
              Page {page} of {totalPages}
            </span>

            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '6px 12px',
                borderRadius: 7,
                border: '1px solid var(--border)',
                background: 'transparent',
                color: page >= totalPages ? 'var(--subtle)' : 'var(--text)',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                fontSize: 12,
              }}
              aria-label="Next page"
            >
              Next
              <ChevronRight size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
