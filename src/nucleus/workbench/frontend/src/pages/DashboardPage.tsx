/**
 * DashboardPage — the Editorial Hero dashboard (root route "/").
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────┐
 *   │  [hero-gradient]  TopNav (transparent, floating)         │
 *   │                   H1 "Today's pipeline"                   │
 *   │                   Stat chips row                          │
 *   ├──────────────────────────────────────────────────────────┤
 *   │  [white body]  Recent Runs | Pipeline DAG | AI Copilot   │
 *   └──────────────────────────────────────────────────────────┘
 *
 * Data source: GET /api/dashboard/summary (single call for hero stats +
 * recent runs). Assets from GET /api/assets for the DAG card.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 * ADR-016 §3 — Fork B layout spec.
 * docs/specs/nucleus_architecture_v4.1.md §8.1 — Layer 4 Experience.
 *
 * # Stability: Internal @ v0.2
 */

import { useQuery } from '@tanstack/react-query';
import { Database, BarChart3, CheckCircle, Clock } from 'lucide-react';
import { fetchDashboardSummary, fetchAssets } from '../lib/api';
import TopNav from '../components/TopNav';
import StatChip from '../components/StatChip';
import RecentRunsCard from '../components/RecentRunsCard';
import PipelineDAGCard from '../components/PipelineDAGCard';
import CopilotCard from '../components/CopilotCard';

/* ── Formatting helpers ───────────────────────────────────────── */

function formatRows(n: number | null): string {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function formatAgo(seconds: number | null): string {
  if (seconds == null) return 'never';
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

/* ── Hero section ─────────────────────────────────────────────── */

function HeroSection() {
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const totalAssets = summary?.total_assets ?? '…';
  const totalRows   = summary != null ? formatRows(summary.total_rows) : '…';
  const greenLabel  = summary != null
    ? `${summary.checks_green}/${summary.checks_total} GREEN`
    : '…';
  const agoLabel    = summary != null ? formatAgo(summary.last_run_ago_seconds) : '…';

  return (
    <section className="hero-gradient" style={{ flexShrink: 0 }}>
      {/* TopNav floats transparently over gradient */}
      <TopNav transparent />

      {/* Hero text */}
      <div style={{ padding: '32px 48px 0' }}>
        <h1
          style={{
            fontSize: 'clamp(56px, 7vw, 100px)',
            fontWeight: 900,
            color: '#ffffff',
            margin: 0,
            lineHeight: 1.02,
            letterSpacing: '-0.04em',
            fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif",
          }}
        >
          Today&apos;s pipeline
        </h1>
      </div>

      {/* Stat chips row — overlaps the hero/body boundary */}
      <div
        style={{
          padding: '24px 48px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          flexWrap: 'wrap',
        }}
        role="region"
        aria-label="Pipeline statistics"
      >
        <div
          className="glass-chip"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 6px',
            borderRadius: 12,
          }}
        >
          <StatChip
            icon={<Database size={14} />}
            label={`${totalAssets} ASSETS`}
            separator
          />
          <StatChip
            icon={<BarChart3 size={14} />}
            label={`${totalRows} ROWS`}
            separator
          />
          <StatChip
            icon={<CheckCircle size={14} />}
            label={greenLabel}
            separator
          />
          <StatChip
            icon={<Clock size={14} />}
            label={agoLabel}
          />
        </div>
      </div>

      {/* Spacer so body starts right below the chips */}
      <div style={{ height: 40 }} />
    </section>
  );
}

/* ── Body 3-column grid ───────────────────────────────────────── */

function BodyGrid() {
  const { data: summary, isLoading: loadingRuns } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const { data: assets = [], isLoading: loadingAssets } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    staleTime: 30_000,
  });

  const recentRuns = summary?.recent_runs ?? [];

  return (
    <section
      style={{
        background: 'var(--bg)',
        padding: '28px 48px 48px',
        display: 'grid',
        gridTemplateColumns: '1fr 1.1fr 1fr',
        gap: 24,
        alignItems: 'start',
      }}
    >
      <RecentRunsCard runs={recentRuns} loading={loadingRuns} />
      <PipelineDAGCard assets={assets} loading={loadingAssets} />
      <CopilotCard />
    </section>
  );
}

/* ── Page ─────────────────────────────────────────────────────── */

export default function DashboardPage() {
  return (
    <div
      className="page-enter"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg)',
      }}
    >
      <HeroSection />
      <BodyGrid />
    </div>
  );
}
