'use client';

import { ChatMessage, Citation } from '@/types/dto';
import { ChatMode } from '@/lib/sse';
import { useState } from 'react';

type Props = {
  mode: ChatMode;
  messages: ChatMessage[];
  streaming: string;
  citations: Citation[];
  onModeChange: (mode: ChatMode) => void;
  onSend: (text: string) => void;
  onSaveToNotes: (text: string) => void;
};

export default function ChatPanel(props: Props) {
  const [input, setInput] = useState('');

  return (
    <section className="flex-1 min-w-0 p-4 bg-slate-50 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Chat</h2>
        <select
          className="rounded border border-slate-300 p-2 text-sm"
          value={props.mode}
          onChange={(event) => props.onModeChange(event.target.value as ChatMode)}
        >
          <option value="qa">QA</option>
          <option value="draft">Draft</option>
          <option value="table">Table</option>
          <option value="summarize">Summarize</option>
        </select>
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
          className="rounded bg-slate-900 px-4 text-white"
          onClick={() => {
            const text = input.trim();
            if (!text) {
              return;
            }
            props.onSend(text);
            setInput('');
          }}
        >
          Send
        </button>
      </div>

      {props.streaming ? (
        <div className="flex items-center gap-2 text-xs">
          <button className="rounded border px-2 py-1" onClick={() => navigator.clipboard.writeText(props.streaming)}>Copy</button>
          <button className="rounded border px-2 py-1" onClick={() => props.onSaveToNotes(props.streaming)}>Save to Notes</button>
          <span className="text-slate-500">Citations: {props.citations.length}</span>
        </div>
      ) : null}
    </section>
  );
}
