// Docs: https://tailwindcss.com/docs/configuration  (tailwindcss==3.4.17)
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['attribute', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        /* Light — Clean Studio (founder-approved palette) */
        'ls-bg':       '#FFFFFF',
        'ls-surface':  '#FAFAFA',
        'ls-border':   '#E5E7EB',
        'ls-primary':  '#4F46E5',
        'ls-success':  '#10B981',
        'ls-warning':  '#F59E0B',
        'ls-error':    '#EF4444',
        'ls-text':     '#0F172A',
        'ls-muted':    '#64748B',
        /* Dark — Dark Workbench (founder-approved palette) */
        'dw-bg':       '#020617',
        'dw-surface':  '#0F172A',
        'dw-surface2': '#1E293B',
        'dw-border':   '#334155',
        'dw-primary':  '#22D3EE',
        'dw-success':  '#34D399',
        'dw-warning':  '#FBBF24',
        'dw-error':    '#F87171',
        'dw-text':     '#F1F5F9',
        'dw-muted':    '#94A3B8',
      },
      boxShadow: {
        'glow-primary': '0 0 24px -8px rgba(34, 211, 238, 0.5)',
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
