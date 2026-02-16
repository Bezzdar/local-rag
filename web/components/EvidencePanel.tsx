'use client';

import { Citation, Note, Source } from '@/types/dto';
import { useMemo, useState } from 'react';
import DocPreview from './DocPreview';

type Props = {
  citations: Citation[];
  notes: Note[];
  sources: Source[];
};

export default function EvidencePanel({ citations, notes, sources }: Props) {
  const [tab, setTab] = useState<'citations' | 'notes'>('citations');
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const source = useMemo(() => sources.find((s) => s.id === activeSourceId) ?? null, [sources, activeSourceId]);

  return (
    <aside className="w-full lg:w-96 border-l bg-white p-4 space-y-3">
      <div className="flex gap-2">
        <button className={`px-3 py-1 rounded ${tab === 'citations' ? 'bg-slate-900 text-white' : 'border'}`} onClick={() => setTab('citations')}>Citations</button>
        <button className={`px-3 py-1 rounded ${tab === 'notes' ? 'bg-slate-900 text-white' : 'border'}`} onClick={() => setTab('notes')}>Notes</button>
      </div>
      {tab === 'citations' ? (
        <div className="space-y-2 max-h-[45vh] overflow-auto">
          {citations.map((c) => <button key={c.id} onClick={() => setActiveSourceId(c.source_id)} className="text-left w-full border rounded p-2"><p className="text-sm">{c.snippet}</p><p className="text-xs text-slate-500">{c.filename} · p.{c.location.page ?? '-'}</p></button>)}
          {citations.length === 0 && <p className="text-sm text-slate-500">Цитат пока нет.</p>}
        </div>
      ) : (
        <div className="space-y-2 max-h-[45vh] overflow-auto">{notes.map((n) => <div key={n.id} className="border rounded p-2"><p className="text-sm font-medium">{n.title}</p><p className="text-xs">{n.content}</p></div>)}{notes.length === 0 && <p className="text-sm text-slate-500">Заметок пока нет.</p>}</div>
      )}
      <DocPreview source={source} />
    </aside>
  );
}
