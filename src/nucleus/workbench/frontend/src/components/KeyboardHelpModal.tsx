/**
 * KeyboardHelpModal — cheatsheet modal triggered by the ``?`` global hotkey.
 *
 * UX audit Rec #7 (2026-05-15) — Databricks SQL Editor + Snowsight both
 * ship a ``?`` cheatsheet listing keyboard shortcuts. Nucleus had Cmd-K
 * / Ctrl-K / ``/`` for the command palette but no discoverable shortcut
 * list; this modal closes that gap.
 *
 * Mounted globally in App.tsx and toggled via the useUIStore
 * ``keyboardHelpOpen`` boolean.
 *
 * # Stability: Internal @ v0.2
 */

import { X } from 'lucide-react';

interface Shortcut {
  keys: string[];
  description: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: ['⌘', 'K'], description: 'Open command palette' },
  { keys: ['Ctrl', 'K'], description: 'Open command palette (Windows / Linux)' },
  { keys: ['/'], description: 'Open command palette (alternate)' },
  { keys: ['⌘', 'Enter'], description: 'Run query (Query Editor only)' },
  { keys: ['Ctrl', 'Enter'], description: 'Run query (Windows / Linux)' },
  { keys: ['?'], description: 'Show this cheatsheet' },
  { keys: ['Esc'], description: 'Close palette / dialog' },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function KeyboardHelpModal({ open, onClose }: Props) {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
        zIndex: 9999,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 440,
          maxWidth: 'calc(100vw - 32px)',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          boxShadow: '0 16px 48px rgba(15, 23, 42, 0.18)',
          padding: 18,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 14,
          }}
        >
          <h2
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--text)',
              margin: 0,
              letterSpacing: '-0.02em',
            }}
          >
            Keyboard shortcuts
          </h2>
          <button
            onClick={onClose}
            aria-label="Close shortcuts modal"
            style={{
              padding: 4,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--muted)',
              display: 'inline-flex',
              alignItems: 'center',
              borderRadius: 6,
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.color = 'var(--text)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.color = 'var(--muted)';
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Shortcut list */}
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {SHORTCUTS.map((s) => (
            <li
              key={s.keys.join('+') + '-' + s.description}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '7px 4px',
                fontSize: 13,
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span style={{ color: 'var(--text)' }}>{s.description}</span>
              <span style={{ display: 'inline-flex', gap: 4 }}>
                {s.keys.map((k, i) => (
                  <kbd
                    key={`${k}-${i}`}
                    style={{
                      padding: '2px 6px',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 4,
                      color: 'var(--text)',
                      lineHeight: 1.2,
                    }}
                  >
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>

        <p
          style={{
            fontSize: 11,
            color: 'var(--muted)',
            marginTop: 12,
            marginBottom: 0,
          }}
        >
          Press <kbd
            style={{
              padding: '1px 5px',
              fontSize: 10,
              fontFamily: 'monospace',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 4,
            }}
          >Esc</kbd> to close.
        </p>
      </div>
    </div>
  );
}
