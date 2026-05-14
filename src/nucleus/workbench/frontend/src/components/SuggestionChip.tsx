/**
 * SuggestionChip — "Try asking" prompt suggestion button in CopilotCard.
 *
 * Clicking the chip pre-fills (or sends) the Copilot input.
 * Per founder visual reference (Editorial Hero v0.2).
 */

import { Sparkles } from 'lucide-react';

interface Props {
  label: string;
  onClick: (label: string) => void;
}

export default function SuggestionChip({ label, onClick }: Props) {
  return (
    <button
      className="suggestion-chip"
      onClick={() => onClick(label)}
      aria-label={`Ask: ${label}`}
    >
      <Sparkles
        size={11}
        style={{ flexShrink: 0, marginTop: 1, color: 'var(--primary)', opacity: 0.7 }}
      />
      <span>{label}</span>
    </button>
  );
}
