'use client';

import { logClientEvent } from '@/lib/clientLogger';
import { ChatMessage, Citation, AgentManifest } from '@/types/dto';
import { CHAT_MODE_OPTIONS, ChatMode } from '@/lib/sse';
import { useMemo, useState } from 'react';

type Props = {
  notebookId: string;
  mode: ChatMode;
  agentId: string;
  agents: AgentManifest[];
  agentsLoading?: boolean;
  agentsError?: string;
  messages: ChatMessage[];
  streaming: string;
  citations: Citation[];
  messageCitations: Map<string, Citation[]>;
  disableSend?: boolean;
  disableClearChat?: boolean;
  clearDisabledReason?: string;
  sendDisabledReason?: string;
  onModeChange: (mode: ChatMode) => void;
  onAgentChange: (agentId: string) => void;
  onSend: (text: string) => void;
  onClearChat: () => void;
  onSaveToNotes: (text: string) => void;
  onCitationClick: (citation: Citation) => void;
};

/**
 * Parse text containing [N] references and return an array of segments.
 * Each segment is either a plain string or a citation reference number.
 */
function parseTextWithCitations(text: string): Array<{ type: 'text'; content: string } | { type: 'ref'; num: number }> {
  const parts: Array<{ type: 'text'; content: string } | { type: 'ref'; num: number }> = [];
  const regex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: 'ref', num: parseInt(match[1], 10) });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return parts;
}

type CitationRefProps = {
  num: number;
  citations: Citation[];
  onClick: (citation: Citation) => void;
};

function CitationRef({ num, citations, onClick }: CitationRefProps) {
  const citation = useMemo(
    () => citations.find((c) => c.doc_order === num),
    [citations, num],
  );

  if (!citation) {
    // No matching citation in current response — show as plain text
    return <span className="text-slate-500">[{num}]</span>;
  }

  return (
    <button
      type="button"
      className="inline-flex items-center justify-center w-6 h-5 rounded bg-blue-600 text-white text-xs font-bold font-mono hover:bg-blue-700 active:bg-blue-800 transition-colors mx-0.5 align-baseline"
      title={`Сохранить цитату из «${citation.filename}» во вкладку Цитаты`}
      onClick={() => onClick(citation)}
    >
      {num}
    </button>
  );
}

type MessageTextProps = {
  text: string;
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
};

type SourceFooterProps = {
  citations: Citation[];
  onClick: (citation: Citation) => void;
};

function SourceFooter({ citations, onClick }: SourceFooterProps) {
  if (citations.length === 0) return null;

  // Deduplicate by doc_order, keep highest score per source
  const unique = new Map<number, Citation>();
  for (const c of citations) {
    const existing = unique.get(c.doc_order);
    if (!existing || c.score > existing.score) {
      unique.set(c.doc_order, c);
    }
  }
  const sorted = Array.from(unique.values()).sort((a, b) => a.doc_order - b.doc_order);

  return (
    <div className="mt-2 pt-2 border-t border-slate-100 flex flex-wrap gap-1 items-center">
      <span className="text-xs text-slate-400">Источники:</span>
      {sorted.map((c) => (
        <button
          key={c.id}
          type="button"
          className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-600 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors"
          title={`Сохранить цитату из «${c.filename}»${c.location?.page ? ` (стр. ${c.location.page})` : ''}`}
          onClick={() => onClick(c)}
        >
          <span className="font-mono font-bold text-blue-600">[{c.doc_order}]</span>
          <span className="truncate max-w-[160px]">{c.filename}</span>
          {c.location?.page ? <span className="text-slate-400">стр. {c.location.page}</span> : null}
        </button>
      ))}
    </div>
  );
}

function MessageText({ text, citations, onCitationClick }: MessageTextProps) {
  const segments = useMemo(() => parseTextWithCitations(text), [text]);

  return (
    <span className="whitespace-pre-wrap">
      {segments.map((seg, idx) =>
        seg.type === 'text' ? (
          <span key={idx}>{seg.content}</span>
        ) : (
          <CitationRef key={idx} num={seg.num} citations={citations} onClick={onCitationClick} />
        ),
      )}
    </span>
  );
}

export default function ChatPanel(props: Props) {
  const [input, setInput] = useState('');

  return (
    <section className="flex-1 min-w-0 p-4 bg-slate-50 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Chat</h2>
        <div className="flex items-center gap-2">
          <button
            className="rounded border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              logClientEvent({ event: 'ui.clear_chat.click', notebookId: props.notebookId, metadata: { mode: props.mode } });
              props.onClearChat();
            }}
            disabled={props.disableClearChat}
            title={props.disableClearChat ? props.clearDisabledReason ?? 'Очистка в процессе…' : undefined}
          >
            Очистить чат
          </button>
          {props.mode === 'agent' && props.agents.length > 0 && (
            <div className="flex items-center gap-1 rounded border border-slate-300 bg-white p-1" title="Выбор агента из манифеста"> 
              {props.agents.map((agent) => {
                const isActive = agent.id === props.agentId;
                return (
                  <button
                    key={agent.id}
                    type="button"
                    className={`rounded px-2 py-1 text-xs transition-colors ${isActive ? 'bg-blue-600 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
                    title={`${agent.description}${agent.tools.length ? ` • tools: ${agent.tools.join(', ')}` : ''}`}
                    onClick={() => {
                      logClientEvent({ event: 'ui.agent.change', notebookId: props.notebookId, metadata: { agentId: agent.id } });
                      props.onAgentChange(agent.id);
                    }}
                  >
                    {agent.name}
                  </button>
                );
              })}
            </div>
          )}
          <select
            className="rounded border border-slate-300 p-2 text-sm"
            value={props.mode}
            onChange={(event) => {
              const nextMode = event.target.value as ChatMode;
              logClientEvent({ event: 'ui.chat_mode.change', notebookId: props.notebookId, metadata: { from: props.mode, to: nextMode } });
              props.onModeChange(nextMode);
            }}
          >
            {CHAT_MODE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-auto space-y-2 min-h-[40vh]">
        {props.messages.length === 0 ? <div className="text-sm text-slate-500">Нет сообщений — начните диалог.</div> : null}
        {props.messages.map((message) => {
          const msgCitations = message.role === 'assistant'
            ? (props.messageCitations.get(message.id) ?? [])
            : [];
          return (
            <div
              key={message.id}
              className={`rounded border p-3 text-sm ${message.role === 'assistant' ? 'bg-white border-slate-200' : 'bg-blue-50 border-blue-200'}`}
            >
              {message.role === 'assistant' ? (
                <div className="space-y-1">
                  <MessageText
                    text={message.content}
                    citations={msgCitations}
                    onCitationClick={props.onCitationClick}
                  />
                  <SourceFooter citations={msgCitations} onClick={props.onCitationClick} />
                  {/* Save-to-notes button under each assistant message */}
                  <div className="flex justify-end pt-1">
                    <button
                      type="button"
                      className="text-slate-400 hover:text-slate-600 transition-colors"
                      title="Сохранить ответ в Заметки"
                      onClick={() => {
                        logClientEvent({ event: 'ui.save_to_notes.message', notebookId: props.notebookId });
                        props.onSaveToNotes(message.content);
                      }}
                    >
                      ↳
                    </button>
                  </div>
                </div>
              ) : (
                message.content
              )}
            </div>
          );
        })}
        {props.streaming ? (
          <div className="rounded border border-slate-200 bg-white p-3 text-sm">
            <MessageText
              text={props.streaming}
              citations={props.citations}
              onCitationClick={props.onCitationClick}
            />
          </div>
        ) : null}
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 p-2"
          placeholder="Спросите по технической документации..."
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              const text = input.trim();
              if (text && !props.disableSend) {
                logClientEvent({ event: 'ui.send.click', notebookId: props.notebookId, metadata: { length: text.length, mode: props.mode } });
                props.onSend(text);
                setInput('');
              }
            }
          }}
        />
        <button
          className="rounded bg-slate-900 px-4 text-white disabled:cursor-not-allowed disabled:opacity-50"
          disabled={props.disableSend}
          title={props.disableSend ? props.sendDisabledReason ?? 'Действие временно недоступно…' : 'Enter — Отправить\nShift + Enter — Перенос строки'}
          onClick={() => {
            const text = input.trim();
            if (!text || props.disableSend) {
              return;
            }
            logClientEvent({ event: 'ui.send.click', notebookId: props.notebookId, metadata: { length: text.length, mode: props.mode } });
            props.onSend(text);
            setInput('');
          }}
        >
          Отправить
        </button>
      </div>

      {props.streaming ? (
        <div className="flex items-center gap-2 text-xs">
          <button className="rounded border px-2 py-1" onClick={() => {
            logClientEvent({ event: 'ui.streaming.copy', notebookId: props.notebookId, metadata: { length: props.streaming.length } });
            navigator.clipboard.writeText(props.streaming);
          }}>Copy</button>
          <button className="rounded border px-2 py-1" onClick={() => {
            logClientEvent({ event: 'ui.save_to_notes.click', notebookId: props.notebookId, metadata: { length: props.streaming.length } });
            props.onSaveToNotes(props.streaming);
          }}>Сохранить в Заметки</button>
          <span className="text-slate-500">Источников: {props.citations.length}</span>
        </div>
      ) : null}
    </section>
  );
}
