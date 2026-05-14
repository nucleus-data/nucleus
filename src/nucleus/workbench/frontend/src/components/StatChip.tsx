/**
 * StatChip — glassmorphism pill chip for the hero stat row.
 *
 * Each chip shows a small icon + uppercase label + value.
 * Rendered inside the hero gradient section with backdrop-filter blur.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 */

import type { ReactNode } from 'react';

interface Props {
  icon: ReactNode;
  label: string;
  /** If true, renders an amber separator dot between this chip and the next. */
  separator?: boolean;
}

export default function StatChip({ icon, label, separator = false }: Props) {
  return (
    <>
      <div
        className="glass-chip"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 7,
          padding: '8px 16px',
          fontSize: 13,
          fontWeight: 600,
          letterSpacing: '0.04em',
          userSelect: 'none',
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ opacity: 0.85, display: 'flex', alignItems: 'center' }}>{icon}</span>
        <span>{label}</span>
      </div>

      {separator && (
        <span
          style={{
            color: 'rgba(255,255,255,0.35)',
            fontSize: 16,
            lineHeight: 1,
            display: 'flex',
            alignItems: 'center',
            userSelect: 'none',
          }}
          aria-hidden="true"
        >
          •
        </span>
      )}
    </>
  );
}
