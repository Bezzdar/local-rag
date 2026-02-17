'use client';

import { Citation, Note, Source } from '@/types/dto';
import { useMemo, useState } from 'react';
import DocPreview from './DocPreview';

type Props = {
  citations: Citation[];
  notes: Note[];
  sources: Source[];
};

export default function EvidencePanel(props: Props) {
  const [tab, setTab] = useState<'citations' | 'notes'>('citations');
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);

  const activeSource = useMemo(
    () => props.sources.find((source) => source.id === activeSourceId) ?? null,
    [props.sources, activeSourceId],
  );

  return (
    <aside className="w-full h-full border-l border-slate-200 bg-white p-4 space-y-3">
      <div className="flex gap-2">
        <button
          className={`rounded px-3 py-1 text-sm ${tab === 'citations' ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}
          onClick={() => setTab('citations')}
        >
          Citations
        </button>
        <button
          className={`rounded px-3 py-1 text-sm ${tab === 'notes' ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}
          onClick={() => setTab('notes')}
        >
          Notes
        </button>
      </div>

      {tab === 'citations' ? (
        <div className="space-y-2 max-h-[45vh] overflow-auto">
          {props.citations.length === 0 ? <p className="text-sm text-slate-500">Цитат нет</p> : null}
          {props.citations.map((citation) => (
            <button
              key={citation.id}
              className="w-full text-left rounded border border-slate-200 p-2"
              onClick={() => setActiveSourceId(citation.source_id)}
            >
              <p className="text-sm">{citation.snippet}</p>
              <p className="text-xs text-slate-500">{citation.filename} · p.{citation.location.page ?? '-'}</p>
            </button>
          ))}
        </div>
      ) : (
        <div className="space-y-2 max-h-[45vh] overflow-auto">
          {props.notes.length === 0 ? <p className="text-sm text-slate-500">Заметок нет</p> : null}
          {props.notes.map((note) => (
            <div key={note.id} className="rounded border border-slate-200 p-2">
              <p className="text-sm font-medium">{note.title}</p>
              <p className="text-xs text-slate-700 whitespace-pre-wrap">{note.content}</p>
            </div>
          ))}
        </div>
      )}

      <DocPreview source={activeSource} />
    </aside>
  );
}
