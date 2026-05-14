/**
 * CommandPalette — ⌘K / Ctrl+K / "/" global search modal.
 *
 * Searches assets, runs, and schedules via GET /api/search.
 * Keyboard navigation: ↑ / ↓ to highlight, Enter to navigate.
 * Escape or backdrop click to close.
 *
 * Per ADR-016 §3 — Fork B layout spec (upgraded from stub in v0.2.0).
 */

import { useEffect, useRef, useState, useDeferredValue } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Database, Play, Clock, BookOpen,
  Code2, LayoutDashboard, Loader2,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { globalSearch } from '../lib/api';
import type { SearchResultItemDTO } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
}

// Static navigation items (always shown when query is empty)
const QUICK_NAV = [
  { label: 'Dashboard',  icon: <LayoutDashboard size={14} />, to: '/' },
  { label: 'Assets',     icon: <Database size={14} />,       to: '/assets' },
  { label: 'Runs',       icon: <Play size={14} />,            to: '/runs' },
  { label: 'Query',      icon: <Code2 size={14} />,           to: '/query' },
  { label: 'Schedules',  icon: <Clock size={14} />,           to: '/schedules' },
  { label: 'Catalog',    icon: <BookOpen size={14} />,        to: '/catalog' },
];

function kindIcon(kind: SearchResultItemDTO['kind']) {
  switch (kind) {
    case 'asset':    return <Database size={13} />;
    case 'run':      return <Play size={13} />;
    case 'schedule': return <Clock size={13} />;
  }
}

export default function CommandPalette({ open, onClose }: Props) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const deferredQuery = useDeferredValue(query);

  // Search API call (debounced via useDeferredValue)
  const { data: searchResults, isFetching } = useQuery({
    queryKey: ['search', deferredQuery],
    queryFn: () => globalSearch(deferredQuery),
    enabled: open && deferredQuery.length >= 2,
    staleTime: 10_000,
  });

  const resultItems = searchResults?.items ?? [];
  const showQuickNav = query.length < 2;

  // Combined list for keyboard navigation
  const activeList: Array<{ label: string; to: string }> = showQuickNav
    ? QUICK_NAV
    : resultItems.map((r) => ({ label: r.label, to: r.url }));

  // Reset state when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [open]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, activeList.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === 'Enter') {
        const item = activeList[activeIndex];
        if (item) { navigate(item.to); onClose(); }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, activeList, activeIndex, navigate, onClose]);

  // Reset active index when list changes
  useEffect(() => {
    setActiveIndex(0);
  }, [deferredQuery, showQuickNav]);

  if (!open) return null;

  function go(to: string) {
    navigate(to);
    onClose();
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '15vh',
        background: 'rgba(10, 14, 26, 0.45)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        style={{
          width: 560,
          maxWidth: 'calc(100vw - 32px)',
          borderRadius: 14,
          border: '1px solid var(--border)',
          background: 'var(--bg)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '14px 18px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {isFetching ? (
            <Loader2 size={15} className="spin" style={{ color: 'var(--muted)', flexShrink: 0 }} />
          ) : (
            <Search size={15} style={{ color: 'var(--muted)', flexShrink: 0 }} />
          )}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIndex(0); }}
            placeholder="Search assets, runs, schedules…"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: 15,
              color: 'var(--text)',
            }}
            aria-label="Search"
            autoComplete="off"
          />
          <kbd
            style={{
              fontSize: 11,
              padding: '2px 6px',
              borderRadius: 5,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--muted)',
              fontFamily: 'inherit',
            }}
          >
            Esc
          </kbd>
        </div>

        {/* Results / nav */}
        <div style={{ padding: '6px 8px', maxHeight: 400, overflow: 'auto' }}>
          {showQuickNav && (
            <>
              <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', padding: '4px 10px 2px', margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Navigate
              </p>
              {QUICK_NAV.map(({ label, icon, to }, i) => (
                <button
                  key={to}
                  onClick={() => go(to)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '9px 10px',
                    borderRadius: 7,
                    border: 'none',
                    background: i === activeIndex ? 'var(--surface)' : 'transparent',
                    color: i === activeIndex ? 'var(--primary)' : 'var(--text)',
                    cursor: 'pointer',
                    fontSize: 13,
                    textAlign: 'left',
                    fontWeight: i === activeIndex ? 600 : 400,
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={() => setActiveIndex(i)}
                >
                  <span style={{ color: 'var(--muted)' }}>{icon}</span>
                  {label}
                </button>
              ))}
            </>
          )}

          {!showQuickNav && (
            <>
              {resultItems.length === 0 && !isFetching && (
                <div style={{ padding: '20px 16px', textAlign: 'center', fontSize: 13, color: 'var(--muted)' }}>
                  No results for &ldquo;{query}&rdquo;
                </div>
              )}

              {resultItems.length > 0 && (
                <>
                  <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', padding: '4px 10px 2px', margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Results
                  </p>
                  {resultItems.map((item, i) => (
                    <button
                      key={`${item.kind}-${item.key}`}
                      onClick={() => go(item.url)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '9px 10px',
                        borderRadius: 7,
                        border: 'none',
                        background: i === activeIndex ? 'var(--surface)' : 'transparent',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={() => setActiveIndex(i)}
                    >
                      <span style={{ color: 'var(--muted)', flexShrink: 0 }}>{kindIcon(item.kind)}</span>
                      <span className="font-mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.label}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>
                        {item.secondary}
                      </span>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '8px 16px',
            borderTop: '1px solid var(--border)',
            fontSize: 11,
            color: 'var(--muted)',
            display: 'flex',
            gap: 16,
          }}
        >
          <span>↑↓ Navigate</span>
          <span>Enter Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
