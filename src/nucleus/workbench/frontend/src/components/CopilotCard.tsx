/**
 * CopilotCard — always-on AI Copilot card (right column of Dashboard).
 *
 * Contains: iridescent BlobAvatar + "AI Copilot" title + … menu,
 * a chat input "Ask anything…" with circular send button,
 * and 3 "Try asking" suggestion chips.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 * ADR-015 §1 — single-turn, opt-in Copilot.
 * ADR-016 §3 — always-on column (not drawer).
 */

import { useRef, useState } from 'react';
import { MoreHorizontal, ArrowRight, Loader2 } from 'lucide-react';
import { askCopilot, ApiError } from '../lib/api';
import type { ChatMessage } from '../types';
import BlobAvatar from './BlobAvatar';
import SuggestionChip from './SuggestionChip';

const SUGGESTIONS = [
  'Why did revenue_daily run longer today?',
  'Show me assets with the most failures',
  'What changed in orders_silver?',
];

export default function CopilotCard() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setLoading(true);

    // Scroll to bottom
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);

    try {
      const reply = await askCopilot({ question: q });
      setMessages((m) => [...m, { role: 'assistant', text: reply.text }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Copilot unavailable. Check your API key.';
      setMessages((m) => [...m, { role: 'assistant', text: `⚠ ${msg}` }]);
    } finally {
      setLoading(false);
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }

  const hasConversation = messages.length > 0;

  return (
    <div
      className="card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 360,
        overflow: 'hidden',
      }}
    >
      {/* Card header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '16px 18px 14px',
          borderBottom: hasConversation ? '1px solid var(--border)' : 'none',
          flexShrink: 0,
        }}
      >
        <BlobAvatar size={32} />
        <span
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: 'var(--text)',
            flex: 1,
            letterSpacing: '-0.01em',
          }}
        >
          AI Copilot
        </span>
        <button
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--muted)',
            padding: 4,
            borderRadius: 5,
            display: 'flex',
            alignItems: 'center',
          }}
          aria-label="Copilot options"
        >
          <MoreHorizontal size={15} />
        </button>
      </div>

      {/* Message thread (shown after first message) */}
      {hasConversation && (
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '12px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '90%',
                padding: '8px 12px',
                borderRadius: m.role === 'user' ? '12px 12px 3px 12px' : '12px 12px 12px 3px',
                background: m.role === 'user' ? 'var(--primary)' : 'var(--surface)',
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
                alignSelf: 'flex-start',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 12px',
                borderRadius: '12px 12px 12px 3px',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                fontSize: 13,
                color: 'var(--muted)',
              }}
            >
              <Loader2 size={12} className="spin" />
              Thinking…
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: hasConversation ? '12px 18px 16px' : '16px 18px',
          borderTop: hasConversation ? '1px solid var(--border)' : 'none',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '8px 8px 8px 14px',
            transition: 'border-color 0.15s',
          }}
          onFocus={() => {/* handled by input */}}
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            disabled={loading}
            placeholder="Ask anything…"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: 13,
              color: 'var(--text)',
              lineHeight: 1.4,
            }}
            aria-label="Ask the AI Copilot"
          />

          {/* Circular send button */}
          <button
            onClick={() => void send()}
            disabled={loading || !input.trim()}
            style={{
              width: 30,
              height: 30,
              borderRadius: '50%',
              border: 'none',
              background: loading || !input.trim() ? 'var(--border)' : 'var(--primary)',
              color: '#fff',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'background 0.15s',
            }}
            aria-label="Send message"
          >
            <ArrowRight size={14} />
          </button>
        </div>

        {/* Suggestion chips (visible when no conversation yet) */}
        {!hasConversation && (
          <div style={{ marginTop: 14 }}>
            <p
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--muted)',
                margin: '0 0 8px',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              Try asking
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {SUGGESTIONS.map((s) => (
                <SuggestionChip
                  key={s}
                  label={s}
                  onClick={(text) => {
                    setInput(text);
                    inputRef.current?.focus();
                    void send(text);
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
