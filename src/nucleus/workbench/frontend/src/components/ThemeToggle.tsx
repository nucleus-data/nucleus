/**
 * ThemeToggle — Sun/Moon icon button to switch between light and dark theme.
 */

import { Sun, Moon } from 'lucide-react';
import type { Theme } from '../lib/theme';

interface Props {
  theme: Theme;
  onToggle: () => void;
}

export default function ThemeToggle({ theme, onToggle }: Props) {
  return (
    <button
      onClick={onToggle}
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme (T)`}
      aria-label="Toggle theme"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 32,
        height: 32,
        borderRadius: 6,
        border: '1px solid var(--border)',
        background: 'transparent',
        color: 'var(--muted)',
        cursor: 'pointer',
      }}
    >
      {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
    </button>
  );
}
