/**
 * NamespacePath — chip rendering of a 2-level Nucleus asset key.
 *
 * UX audit Rec #5 (2026-05-15) — Catalog 3-level chip familiarity:
 *
 *   Databricks Unity Catalog renders `<catalog>.<schema>.<table>` as a
 *   3-chip path with a copy-on-click button. Snowsight renders
 *   `<database>.<schema>.<object>` the same way. Nucleus is 2-level in
 *   v0.1/v0.2 (catalog landing at v0.3 with Lakekeeper) — we render the
 *   2-level form as `<namespace> · <name>` with the same chip-hierarchy
 *   visual cue so DB/SF converts immediately recognise the pattern.
 *
 * Per `docs/research/ux_familiarity_audit.md` §Rec 5.
 *
 * # Stability: Internal @ v0.2
 */

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface Props {
  /** Full asset key, e.g. ``raw.orders`` */
  fullKey: string;
  /** First segment, e.g. ``raw`` */
  namespace: string;
}

export default function NamespacePath({ fullKey, namespace }: Props) {
  const [copied, setCopied] = useState(false);

  // Last segment is everything after the first dot. Falls back to fullKey
  // when no dot is present (e.g. legacy single-segment keys).
  const name = fullKey.includes('.') ? fullKey.slice(namespace.length + 1) : fullKey;

  function handleCopy(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(fullKey).then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1100);
      });
    }
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontFamily: 'monospace',
        fontSize: 13,
        whiteSpace: 'nowrap',
      }}
      title={fullKey}
    >
      {/* Namespace chip (muted) */}
      <span
        style={{
          padding: '1px 6px',
          borderRadius: 4,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          color: 'var(--muted)',
          fontWeight: 500,
          fontSize: 11,
        }}
        aria-label={`Namespace ${namespace}`}
      >
        {namespace}
      </span>

      <span style={{ color: 'var(--muted)', fontSize: 11, opacity: 0.7 }}>·</span>

      {/* Name chip (bold) */}
      <span
        style={{
          fontWeight: 600,
          color: 'var(--text)',
        }}
        aria-label={`Asset name ${name}`}
      >
        {name}
      </span>

      {/* Copy-full-key button */}
      <button
        onClick={handleCopy}
        title={copied ? 'Copied!' : 'Copy full key'}
        aria-label={copied ? 'Copied to clipboard' : 'Copy full asset key'}
        style={{
          marginLeft: 2,
          padding: 2,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: copied ? 'var(--success)' : 'var(--muted)',
          display: 'inline-flex',
          alignItems: 'center',
          borderRadius: 4,
          transition: 'color 0.15s',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.color = copied
            ? 'var(--success)'
            : 'var(--text)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.color = copied
            ? 'var(--success)'
            : 'var(--muted)';
        }}
      >
        {copied ? <Check size={11} /> : <Copy size={11} />}
      </button>
    </span>
  );
}
