'use client';

import { logClientEvent } from '@/lib/clientLogger';
import { ChatMessage, Citation, AgentManifest } from '@/types/dto';
import { CHAT_MODE_OPTIONS, ChatMode } from '@/lib/sse';
import { useState } from 'react';

type Props = {
  notebookId: string;
  mode: ChatMode;
  agentId: string;
  agents: AgentManifest[];
  messages: ChatMessage[];
  streaming: string;
  citations: Citation[];
  disableSend?: boolean;
  disableClearChat?: boolean;
  clearDisabledReason?: string;
  sendDisabledReason?: string;
  onModeChange: (mode: ChatMode) => void;
  onAgentChange: (agentId: string) => void;
  onSend: (text: string) => void;
  onClearChat: () => void;
  onSaveToNotes: (text: string) => void;
};

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
            <select
              className="rounded border border-slate-300 p-2 text-sm"
              value={props.agentId}
              onChange={(event) => {
                logClientEvent({ event: 'ui.agent.change', notebookId: props.notebookId, metadata: { agentId: event.target.value } });
                props.onAgentChange(event.target.value);
              }}
            >
              {props.agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
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
        {props.messages.map((message) => (
          <div
            key={message.id}
            className={`rounded border p-3 text-sm ${message.role === 'assistant' ? 'bg-white border-slate-200' : 'bg-blue-50 border-blue-200'}`}
          >
            {message.content}
          </div>
        ))}
        {props.streaming ? <div className="rounded border border-slate-200 bg-white p-3 text-sm whitespace-pre-wrap">{props.streaming}</div> : null}
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 p-2"
          placeholder="Спросите по технической документации..."
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />
        <button
          className="rounded bg-slate-900 px-4 text-white disabled:cursor-not-allowed disabled:opacity-50"
          disabled={props.disableSend}
          title={props.disableSend ? props.sendDisabledReason ?? 'Действие временно недоступно…' : undefined}
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
          Send
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
          }}>Save to Notes</button>
          <span className="text-slate-500">Citations: {props.citations.length}</span>
        </div>
      ) : null}
    </section>
  );
}
