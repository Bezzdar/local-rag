'use client';

import { ChatMessage, Citation } from '@/types/dto';
import { useState } from 'react';

type Props = {
  messages: ChatMessage[];
  streamingText: string;
  mode: 'qa' | 'draft' | 'table' | 'summarize';
  onModeChange: (mode: 'qa' | 'draft' | 'table' | 'summarize') => void;
  onSend: (text: string) => void;
  onSaveToNotes: (text: string) => void;
  citations: Citation[];
};

export default function ChatPanel({ messages, streamingText, mode, onModeChange, onSend, onSaveToNotes, citations }: Props) {
  const [input, setInput] = useState('');

  return (
    <main className="flex-1 p-4 flex flex-col gap-3 bg-slate-50">
      <div className="flex justify-between items-center">
        <h2 className="font-semibold">Chat</h2>
        <select value={mode} onChange={(e) => onModeChange(e.target.value as Props['mode'])} className="border rounded p-2">
          <option value="qa">QA</option><option value="draft">Draft</option><option value="table">Table</option><option value="summarize">Summarize</option>
        </select>
      </div>
      <div className="flex-1 overflow-auto space-y-3">
        {messages.length === 0 && <div className="text-sm text-slate-500">Начните диалог по техдокументации.</div>}
        {messages.map((m) => <div key={m.id} className={`p-3 rounded ${m.role === 'assistant' ? 'bg-white border' : 'bg-blue-50 border-blue-200 border'}`}><p className="text-sm">{m.content}</p></div>)}
        {streamingText && <div className="p-3 rounded bg-white border"><p className="text-sm whitespace-pre-wrap">{streamingText}</p></div>}
      </div>
      <div className="flex gap-2">
        <input className="border rounded p-2 flex-1" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Спросите по документам..." />
        <button className="bg-slate-900 text-white rounded px-4" onClick={() => { if (input.trim()) { onSend(input.trim()); setInput(''); } }}>Send</button>
      </div>
      {streamingText && <div className="flex gap-2"><button className="text-xs border rounded px-2 py-1" onClick={() => navigator.clipboard.writeText(streamingText)}>Copy</button><button className="text-xs border rounded px-2 py-1" onClick={() => onSaveToNotes(streamingText)}>Save to Notes</button><span className="text-xs text-slate-500">Citations: {citations.length}</span></div>}
    </main>
  );
}
