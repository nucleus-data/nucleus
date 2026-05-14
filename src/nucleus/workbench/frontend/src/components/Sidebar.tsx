/**
 * Sidebar — 240px fixed left navigation.
 *
 * Shows: logo block, nav links (Assets / Runs / Query), and a footer
 * count of registered assets.
 *
 * Per ADR-016 §3 layout spec.
 */

import { Database, Play, Code2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchAssets } from '../lib/api';

export default function Sidebar() {
  const { data: assets } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    staleTime: 30_000,
  });

  const navItems = [
    { to: '/assets', icon: <Database size={14} />, label: 'Assets' },
    { to: '/runs',   icon: <Play size={14} />,     label: 'Runs' },
    { to: '/query',  icon: <Code2 size={14} />,    label: 'Query' },
  ];

  return (
    <aside
      style={{
        width: 240,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
      }}
    >
      {/* Brand block */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '14px 16px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <Database size={17} style={{ color: 'var(--primary)' }} />
        <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>
          Nucleus
        </span>
      </div>

      {/* Navigation */}
      <nav style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {navItems.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 10px',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              textDecoration: 'none',
              background: isActive ? 'var(--primary)' : 'transparent',
              color: isActive ? '#fff' : 'var(--muted)',
              transition: 'background 0.12s, color 0.12s',
            })}
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ marginTop: 'auto', padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: 11, color: 'var(--muted)', margin: 0 }}>
          {assets ? `${assets.length} asset${assets.length !== 1 ? 's' : ''} registered` : 'Loading…'}
        </p>
      </div>
    </aside>
  );
}
