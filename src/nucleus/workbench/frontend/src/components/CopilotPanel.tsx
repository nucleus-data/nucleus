/**
 * CopilotPanel — right-side AI Copilot chat drawer.
 *
 * Slide-in panel (~480px wide) with a message list and input bar.
 * Calls POST /api/chat on each message.
 *
 * Toggled via the Copilot button in Header.tsx.
 * Per ADR-016 §3 + ADR-015 §1 (single-turn, opt-in).
 */

import { useEffect, useRef, useState } from 'react';
import { Sparkles, Send, Loader2, X } from 'lucide-react';
import { askCopilot, ApiError } from '../lib/api';
import type { ChatMessage } from '../types';

interface Props {
  open: boolean;
}

export default function CopilotPanel({ open }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text: "Hi! I'm the Nucleus Copilot. Ask me about your assets, SQL patterns, schema evolution, or how to run the CLI.",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const reply = await askCopilot({ question: q });
      setMessages((m) => [...m, { role: 'assistant', text: reply.text }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setMessages((m) => [...m, { role: 'assistant', text: `⚠ ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <aside
      style={{
        width: open ? 480 : 0,
        flexShrink: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: open ? '1px solid var(--border)' : 'none',
        background: 'var(--surface)',
        transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
      }}
      aria-hidden={!open}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '12px 16px', borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <Sparkles size={15} style={{ color: 'var(--primary)' }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flex: 1 }}>
          AI Copilot
        </span>
        <span
          style={{
            fontSize: 10, padding: '1px 6px', borderRadius: 9999,
            background: 'var(--border)', color: 'var(--muted)', fontWeight: 600,
          }}
        >
          Beta
        </span>
        <button
          onClick={() => setMessages([{ role: 'assistant', text: "Conversation cleared. How can I help?" }])}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--muted)', padding: 2 }}
          title="Clear conversation"
        >
          <X size={13} />
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1, overflow: 'auto', padding: 16,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}
      >
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              padding: '8px 12px',
              borderRadius: m.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              background: m.role === 'user' ? 'var(--primary)' : 'var(--bg)',
              color: m.role === 'user' ? '#fff' : 'var(--text)',
              border: m.role === 'user' ? 'none' : '1px solid var(--border)',
              fontSize: 13,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {m.text}
          </div>
        ))}

        {loading && (
          <div
            style={{
              alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 12px', borderRadius: '12px 12px 12px 4px',
              background: 'var(--bg)', border: '1px solid var(--border)',
              fontSize: 13, color: 'var(--muted)',
            }}
          >
            <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
            Thinking…
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 12px', borderTop: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="Ask about your assets…"
          style={{
            flex: 1, border: '1px solid var(--border)', borderRadius: 8,
            padding: '7px 12px', fontSize: 13, outline: 'none',
            background: 'var(--bg)', color: 'var(--text)',
          }}
        />
        <button
          onClick={() => void send()}
          disabled={loading || !input.trim()}
          style={{
            width: 34, height: 34, borderRadius: 8, border: 'none',
            background: 'var(--primary)', color: '#fff',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
        >
          <Send size={14} />
        </button>
      </div>
    </aside>
  );
}
