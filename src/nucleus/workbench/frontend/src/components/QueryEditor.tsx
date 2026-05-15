/**
 * QueryEditor — Monaco SQL editor + results table.
 *
 * Uses @monaco-editor/react (which lazy-loads Monaco from cdn.jsdelivr.net
 * or from node_modules/monaco-editor when available).
 *
 * Docs: https://github.com/suren-atoyan/monaco-react  (@monaco-editor/react==4.6.0)
 *
 * Theme tokens are injected via defineTheme so Monaco matches the app palette.
 */

import { useState, useCallback, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { Play, Loader2, AlertCircle, Table2 } from 'lucide-react';
import type { QueryResultDTO } from '../types';
import { executeQuery, ApiError } from '../lib/api';

const PLACEHOLDER = `-- Nucleus Query Editor
-- Use {{ ref('schema.name') }} to reference registered assets.

SELECT 1 AS hello, 'nucleus' AS platform`;

export default function QueryEditor() {
  // Editorial light theme only (dark mode descoped in v0.2 per founder directive).
  const theme = 'light';
  const [sql, setSql] = useState(PLACEHOLDER);
  const [result, setResult] = useState<QueryResultDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // UX audit Rec #7 (2026-05-15): ``run`` is held in a ref so Monaco's
  // ``addCommand`` (registered once at mount time) always invokes the
  // freshest version. Without this the keybinding captures the initial
  // closure and Cmd-Enter would race against stale ``sql`` state.
  const runRef = useRef<(() => Promise<void>) | null>(null);

  const run = useCallback(async () => {
    const q = sql.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await executeQuery(q);
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message}${e.fixHint ? '\n\nFix: ' + e.fixHint : ''}` : String(e));
    } finally {
      setLoading(false);
    }
  }, [sql, loading]);

  // Keep the ref pointing at the latest ``run`` callback.
  runRef.current = run;

  const monacoTheme = theme === 'dark' ? 'nucleus-dark' : 'nucleus-light';

  function handleEditorMount(
    editor: { addCommand: (keybinding: number, handler: () => void) => void },
    monaco: {
      KeyMod: { CtrlCmd: number };
      KeyCode: { Enter: number };
      editor: { defineTheme: (name: string, def: unknown) => void };
    },
  ) {
    // UX audit Rec #7 — Cmd/Ctrl+Enter inside Monaco invokes the latest run
    // closure via the ref. Match the Snowsight + Databricks SQL Editor
    // convention; the existing toolbar hint already advertises ⌘Enter.
    // Docs: https://microsoft.github.io/monaco-editor/api/interfaces/monaco.editor.ICodeEditor.html#addCommand
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      void runRef.current?.();
    });

    monaco.editor.defineTheme('nucleus-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#020617',
        'editor.foreground': '#F1F5F9',
        'editor.lineHighlightBackground': '#0F172A',
        'editorLineNumber.foreground': '#334155',
        'editorCursor.foreground': '#22D3EE',
      },
    });
    monaco.editor.defineTheme('nucleus-light', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#FAFAFA',
        'editor.foreground': '#0F172A',
        'editor.lineHighlightBackground': '#F0F4FF',
        'editorLineNumber.foreground': '#94A3B8',
        'editorCursor.foreground': '#4F46E5',
      },
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', padding: 20, gap: 12 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <h1 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>Query Editor</h1>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
          ⌘Enter to run
        </span>
        <button
          onClick={run}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 6, border: 'none',
            background: 'var(--primary)', color: '#fff',
            cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: 13,
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={13} />}
          Run
        </button>
      </div>

      {/* Monaco editor */}
      <div
        style={{
          borderRadius: 8, border: '1px solid var(--border)',
          overflow: 'hidden', flexShrink: 0, height: 200,
        }}
      >
        <Editor
          height={200}
          language="sql"
          value={sql}
          theme={monacoTheme}
          onChange={(val) => setSql(val ?? '')}
          onMount={handleEditorMount}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            padding: { top: 10, bottom: 10 },
            renderLineHighlight: 'line',
          }}
        />
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            padding: 12, borderRadius: 8, border: '1px solid var(--error)',
            background: 'rgba(239,68,68,.08)', color: 'var(--error)',
            fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
          }}
        >
          <AlertCircle size={13} style={{ display: 'inline', marginRight: 6 }} />
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ flex: 1, borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {/* Results header */}
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 12px', borderBottom: '1px solid var(--border)',
              background: 'var(--surface)', fontSize: 11, color: 'var(--muted)',
            }}
          >
            <Table2 size={12} />
            <span>{result.row_count} row{result.row_count !== 1 ? 's' : ''}</span>
            {result.truncated && (
              <span style={{ marginLeft: 4, fontSize: 10, background: 'var(--border)', borderRadius: 4, padding: '1px 5px' }}>
                truncated
              </span>
            )}
          </div>

          {/* Results table */}
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
                  {result.columns.map((col) => (
                    <th
                      key={col}
                      style={{
                        padding: '6px 12px', textAlign: 'left', fontSize: 11,
                        fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: i < result.rows.length - 1 ? '1px solid var(--border)' : 'none' }}
                  >
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        style={{
                          padding: '5px 12px', fontFamily: 'monospace',
                          color: 'var(--text)', whiteSpace: 'nowrap',
                        }}
                      >
                        {cell === null ? (
                          <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>null</span>
                        ) : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
