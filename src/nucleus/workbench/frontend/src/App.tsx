/**
 * App.tsx — root component with router + global UI state.
 *
 * Route shape (Editorial Hero v0.2 — per founder mockup):
 *   /                  — Dashboard (Editorial Hero + 3-column grid) ← default
 *   /assets            — Asset Explorer (tree + DAG + detail)
 *   /assets/:key       — Asset Detail drilldown
 *   /runs              — Run history table
 *   /runs/:run_id      — Run Detail log viewer
 *   /query             — SQL Query Editor
 *   /schedules         — Schedule list + next-run preview
 *   /catalog           — Asset catalog browser (table view)
 *
 * Per ADR-016 §3 (Fork B) + nucleus_architecture_v4.1.md §8.1.
 *
 * # Stability: Internal @ v0.2
 */

import { Suspense, lazy, useCallback, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { create } from 'zustand';
import KeyboardHelpModal from './components/KeyboardHelpModal';

// Docs: https://docs.pmnd.rs/zustand/getting-started/introduction (zustand==5.0.2)

/* ── Lazy-loaded pages for code splitting ─────────────────────── */
const DashboardPage   = lazy(() => import('./pages/DashboardPage'));
const AssetsPage      = lazy(() => import('./pages/AssetsPage'));
const AssetDetailPage = lazy(() => import('./pages/AssetDetailPage'));
const RunsPage        = lazy(() => import('./pages/RunsPage'));
const RunDetailPage   = lazy(() => import('./pages/RunDetailPage'));
const QueryPage       = lazy(() => import('./pages/QueryPage'));
const SchedulesPage   = lazy(() => import('./pages/SchedulesPage'));
const CatalogPage     = lazy(() => import('./pages/CatalogPage'));

/* ── Global UI state ──────────────────────────────────────────── */

interface UIState {
  selectedAssetKey: string | null;
  commandPaletteOpen: boolean;
  keyboardHelpOpen: boolean;
  setSelectedAsset: (key: string | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  setKeyboardHelpOpen: (open: boolean) => void;
  toggleKeyboardHelp: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  selectedAssetKey: null,
  commandPaletteOpen: false,
  keyboardHelpOpen: false,
  setSelectedAsset: (key) => set({ selectedAssetKey: key }),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  toggleCommandPalette: () => set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),
  setKeyboardHelpOpen: (open) => set({ keyboardHelpOpen: open }),
  toggleKeyboardHelp: () => set((s) => ({ keyboardHelpOpen: !s.keyboardHelpOpen })),
}));

/* ── Page loading fallback ────────────────────────────────────── */
function PageSkeleton() {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--muted)',
        fontSize: 13,
      }}
    >
      <div className="skeleton" style={{ width: 200, height: 16, borderRadius: 8 }} />
    </div>
  );
}

/* ── Root router ──────────────────────────────────────────────── */

function AppRoutes() {
  const {
    toggleCommandPalette,
    keyboardHelpOpen,
    setKeyboardHelpOpen,
    toggleKeyboardHelp,
  } = useUIStore();

  // Global keyboard shortcuts
  const handleGlobalKey = useCallback(
    (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA';

      // Esc — close any open global modal (kept outside the INPUT guard
      // so it works even while a search box has focus).
      if (e.key === 'Escape' && keyboardHelpOpen) {
        e.preventDefault();
        setKeyboardHelpOpen(false);
        return;
      }

      if (isInput) return;

      // ⌘K / Ctrl+K — command palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
        return;
      }
      // / — focus search (same as ⌘K)
      if (e.key === '/' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        toggleCommandPalette();
        return;
      }
      // ? — keyboard help cheatsheet (UX audit Rec #7, 2026-05-15).
      //   Shift+? on US layouts produces `?`; we match by the produced char
      //   instead of `Shift+/` because key codes differ across keyboards.
      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        toggleKeyboardHelp();
      }
    },
    [toggleCommandPalette, toggleKeyboardHelp, setKeyboardHelpOpen, keyboardHelpOpen],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleGlobalKey);
    return () => window.removeEventListener('keydown', handleGlobalKey);
  }, [handleGlobalKey]);

  return (
    <>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/"              element={<DashboardPage />} />
          <Route path="/assets"        element={<AssetsPage />} />
          <Route path="/assets/:key"   element={<AssetDetailPage />} />
          <Route path="/runs"          element={<RunsPage />} />
          <Route path="/runs/:run_id"  element={<RunDetailPage />} />
          <Route path="/query"         element={<QueryPage />} />
          <Route path="/schedules"     element={<SchedulesPage />} />
          <Route path="/catalog"       element={<CatalogPage />} />
          {/* Legacy redirect: old default was /assets */}
          <Route path="*"              element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>

      {/* UX audit Rec #7 — globally mounted shortcut cheatsheet */}
      <KeyboardHelpModal
        open={keyboardHelpOpen}
        onClose={() => setKeyboardHelpOpen(false)}
      />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
