/**
 * TopNav — transparent top navigation bar (floats over hero on Dashboard;
 * solid white on all other pages).
 *
 * Shows: nucleus logo + slash + project selector chevron (left),
 * notification bell + user avatar (right).
 *
 * Per founder visual reference (Editorial Hero v0.2).
 * ADR-016 §3 — Fork B layout spec.
 */

import { useState } from 'react';
import { Bell, ChevronDown, Database, Search, Terminal } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useUIStore } from '../App';
import CommandPalette from './CommandPalette';

interface Props {
  /** When true: renders with transparent background, white text (over hero gradient). */
  transparent?: boolean;
  /** Project display name (defaults to inferring from URL or 'my_warehouse'). */
  projectName?: string;
}

const NAV_LINKS = [
  { to: '/',          label: 'Dashboard' },
  { to: '/assets',    label: 'Assets' },
  { to: '/runs',      label: 'Runs' },
  { to: '/query',     label: 'Query' },
  { to: '/schedules', label: 'Schedules' },
  { to: '/catalog',   label: 'Catalog' },
] as const;

export default function TopNav({ transparent = false, projectName = 'my_warehouse' }: Props) {
  const { commandPaletteOpen, setCommandPaletteOpen, toggleCommandPalette } = useUIStore();
  const navigate = useNavigate();
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);

  const textColor = transparent ? 'rgba(255,255,255,0.95)' : 'var(--text)';
  const mutedColor = transparent ? 'rgba(255,255,255,0.65)' : 'var(--muted)';
  const borderColor = transparent ? 'rgba(255,255,255,0.15)' : 'var(--border)';
  const hoverBg = transparent ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.04)';

  return (
    <>
      <nav
        className={transparent ? 'topnav-hero' : 'topnav-solid'}
        style={{
          display: 'flex',
          alignItems: 'center',
          height: 56,
          padding: '0 28px',
          gap: 8,
          position: 'relative',
          zIndex: 20,
          flexShrink: 0,
        }}
      >
        {/* Logo + project selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          <button
            onClick={() => navigate('/')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 6,
            }}
            aria-label="Go to Dashboard"
          >
            <Database
              size={16}
              style={{ color: transparent ? '#fff' : 'var(--primary)', flexShrink: 0 }}
            />
            <span
              style={{
                fontWeight: 700,
                fontSize: 14,
                color: textColor,
                letterSpacing: '-0.01em',
              }}
            >
              nucleus
            </span>
          </button>

          {/* Slash + project dropdown */}
          <span style={{ color: mutedColor, margin: '0 2px', fontSize: 16, fontWeight: 300 }}>/</span>
          <button
            onClick={() => setProjectMenuOpen((o) => !o)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              background: projectMenuOpen ? hoverBg : 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 500,
              color: textColor,
              transition: 'background 0.15s',
            }}
            aria-haspopup="true"
            aria-expanded={projectMenuOpen}
          >
            {projectName}
            <ChevronDown size={14} style={{ opacity: 0.7 }} />
          </button>
        </div>

        {/* Page nav links (middle, compact) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginLeft: 16 }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                color: isActive
                  ? textColor
                  : mutedColor,
                textDecoration: 'none',
                padding: '5px 10px',
                borderRadius: 6,
                background: isActive ? hoverBg : 'transparent',
                transition: 'background 0.12s, color 0.12s',
              })}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = hoverBg;
              }}
              onMouseLeave={(e) => {
                // Let NavLink handle active state; only clear for inactive
                const el = e.currentTarget as HTMLElement;
                if (!el.classList.contains('active')) {
                  el.style.background = 'transparent';
                }
              }}
            >
              {label}
            </NavLink>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Search / ⌘K trigger */}
        <button
          onClick={toggleCommandPalette}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 12px',
            borderRadius: 7,
            border: `1px solid ${borderColor}`,
            background: transparent ? 'rgba(255,255,255,0.08)' : 'var(--surface)',
            color: mutedColor,
            cursor: 'pointer',
            fontSize: 12,
          }}
          aria-label="Open command palette (⌘K)"
        >
          <Search size={13} />
          <span>Search…</span>
          <kbd
            style={{
              marginLeft: 6,
              fontSize: 10,
              padding: '1px 5px',
              borderRadius: 4,
              border: `1px solid ${borderColor}`,
              background: transparent ? 'rgba(255,255,255,0.10)' : 'var(--bg)',
              color: mutedColor,
              fontFamily: 'inherit',
            }}
          >
            ⌘K
          </kbd>
        </button>

        {/* Notification bell */}
        <button
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            border: `1px solid ${borderColor}`,
            background: transparent ? 'rgba(255,255,255,0.08)' : 'var(--surface)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: mutedColor,
          }}
          aria-label="Notifications"
        >
          <Bell size={15} />
        </button>

        {/* User avatar */}
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: '50%',
            background: transparent
              ? 'rgba(255,255,255,0.20)'
              : 'linear-gradient(135deg, #4F75FF, #7C3AED)',
            border: `2px solid ${borderColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            overflow: 'hidden',
            flexShrink: 0,
          }}
          role="button"
          tabIndex={0}
          aria-label="User profile"
        >
          <Terminal size={15} style={{ color: transparent ? '#fff' : '#fff' }} />
        </div>
      </nav>

      {/* Global Command Palette */}
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </>
  );
}
