/**
 * Header — top navigation bar.
 *
 * Contains: project name, search stub (⌘K — opens CommandPalette),
 * theme toggle, and AI Copilot panel toggle.
 *
 * Per ADR-016 §3 layout spec.
 */

import { Sparkles, Search } from 'lucide-react';
import type { Theme } from '../lib/theme';
import ThemeToggle from './ThemeToggle';
import CommandPalette from './CommandPalette';
import { useState } from 'react';

interface Props {
  theme: Theme;
  onThemeToggle: () => void;
  copilotOpen: boolean;
  onCopilotToggle: () => void;
}

export default function Header({ theme, onThemeToggle, copilotOpen, onCopilotToggle }: Props) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  return (
    <>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '0 20px',
          height: 52,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
          flexShrink: 0,
        }}
      >
        {/* Logo / project name */}
        <span
          style={{
            fontWeight: 700,
            fontSize: 14,
            color: 'var(--primary)',
            letterSpacing: '-0.02em',
          }}
        >
          Nucleus
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--muted)',
            background: 'var(--border)',
            borderRadius: 4,
            padding: '1px 6px',
            fontWeight: 600,
          }}
        >
          Workbench v0.2
        </span>

        {/* Search button (⌘K stub) */}
        <button
          onClick={() => setPaletteOpen(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg)',
            color: 'var(--muted)',
            cursor: 'pointer',
            fontSize: 12,
            marginLeft: 8,
          }}
          aria-label="Open command palette (⌘K)"
        >
          <Search size={13} />
          <span>Search…</span>
          <kbd
            style={{
              marginLeft: 8,
              fontSize: 10,
              padding: '1px 4px',
              borderRadius: 3,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
            }}
          >
            ⌘K
          </kbd>
        </button>

        <div style={{ flex: 1 }} />

        <ThemeToggle theme={theme} onToggle={onThemeToggle} />

        {/* Copilot toggle */}
        <button
          onClick={onCopilotToggle}
          aria-label="Toggle AI Copilot"
          aria-pressed={copilotOpen}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 12px',
            borderRadius: 6,
            border: 'none',
            background: copilotOpen ? 'var(--primary)' : 'var(--border)',
            color: copilotOpen ? '#fff' : 'var(--text)',
            cursor: 'pointer',
            fontSize: 12,
            fontWeight: 600,
            transition: 'background 0.15s, color 0.15s',
          }}
        >
          <Sparkles size={13} />
          Copilot
        </button>
      </header>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
