'use client';

import { useMemo, useState } from 'react';
import { Notebook, Source } from '@/types/dto';

type Props = {
  notebooks: Notebook[];
  activeNotebookId: string;
  sources: Source[];
  selectedSourceIds: string[];
  onNotebookChange: (id: string) => void;
  onCreateNotebook: (title: string) => void;
  onToggleSource: (id: string) => void;
  onUpload: (file: File) => void;
};

export default function SourcesPanel(props: Props) {
  const [newTitle, setNewTitle] = useState('');
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => props.sources.filter((s) => s.filename.toLowerCase().includes(query.toLowerCase())), [props.sources, query]);

  return (
    <aside className="w-full lg:w-80 border-r bg-white p-4 space-y-3">
      <select className="w-full border rounded p-2" value={props.activeNotebookId} onChange={(e) => props.onNotebookChange(e.target.value)}>
        {props.notebooks.map((n) => <option key={n.id} value={n.id}>{n.title}</option>)}
      </select>
      <div className="flex gap-2">
        <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="New notebook" className="border rounded p-2 flex-1" />
        <button className="px-3 rounded bg-slate-900 text-white" onClick={() => { if (newTitle.trim()) props.onCreateNotebook(newTitle.trim()); setNewTitle(''); }}>+</button>
      </div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search sources" className="border rounded p-2 w-full" />
      <label className="block border rounded p-2 text-sm cursor-pointer">
        Upload file
        <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && props.onUpload(e.target.files[0])} />
      </label>
      <div className="space-y-2 max-h-[60vh] overflow-auto">
        {filtered.length === 0 && <p className="text-sm text-slate-500">Нет источников.</p>}
        {filtered.map((s) => (
          <label key={s.id} className="flex items-start gap-2 border rounded p-2">
            <input type="checkbox" checked={props.selectedSourceIds.includes(s.id)} onChange={() => props.onToggleSource(s.id)} />
            <div>
              <p className="text-sm font-medium">{s.filename}</p>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100">{s.status}</span>
            </div>
          </label>
        ))}
      </div>
    </aside>
  );
}
