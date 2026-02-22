'use client';

import { GlobalNote, SavedCitation, Source } from '@/types/dto';
import { useState } from 'react';

type Props = {
  savedCitations: SavedCitation[];
  globalNotes: GlobalNote[];
  sources: Source[];
  onDeleteCitation: (citation: SavedCitation) => void;
  onDeleteNote: (note: GlobalNote) => void;
  onOpenSource: (sourceId: string) => void;
};

export default function EvidencePanel(props: Props) {
  const [tab, setTab] = useState<'citations' | 'notes'>('citations');

  return (
    <aside className="w-full h-full border-l border-slate-200 bg-white p-4 space-y-3">
      <div className="flex gap-2">
        <button
          className={`rounded px-3 py-1 text-sm ${tab === 'citations' ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}
          onClick={() => setTab('citations')}
        >
          Цитаты
        </button>
        <button
          className={`rounded px-3 py-1 text-sm ${tab === 'notes' ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}
          onClick={() => setTab('notes')}
        >
          Заметки
        </button>
      </div>

      {tab === 'citations' ? (
        <div className="space-y-2 max-h-[60vh] overflow-auto">
          {props.savedCitations.length === 0 ? (
            <p className="text-sm text-slate-500">
              Нет сохранённых цитат. Нажмите на номер источника [{'{N}'}] в ответе чата, чтобы сохранить цитату.
            </p>
          ) : null}
          {props.savedCitations.map((citation) => (
            <div key={citation.id} className="rounded border border-slate-200 p-2 space-y-1 relative">
              {/* Document title with number */}
              <div className="flex items-start justify-between gap-1">
                <p className="text-xs font-semibold text-slate-700 leading-tight">
                  <span className="inline-flex items-center justify-center w-5 h-4 rounded bg-slate-700 text-white text-xs font-mono font-bold mr-1">
                    {citation.doc_order}
                  </span>
                  {citation.filename}
                  {citation.location?.page ? ` · стр. ${citation.location.page}` : ''}
                </p>
                <button
                  type="button"
                  className="shrink-0 text-slate-400 hover:text-red-500 transition-colors text-sm leading-none"
                  title="Удалить цитату"
                  onClick={() => props.onDeleteCitation(citation)}
                >
                  ✕
                </button>
              </div>
              {/* Chunk text */}
              <p className="text-xs text-slate-600 whitespace-pre-wrap leading-relaxed">{citation.chunk_text}</p>
              {/* Source traceability */}
              <p className="text-xs text-slate-400">
                Источник: {citation.source_type === 'notebook' ? 'Ноутбук' : 'БД'} · {citation.source_notebook_id.slice(0, 8)}…
              </p>
              {/* Open document with OS default application */}
              <button
                type="button"
                className="text-xs text-blue-600 hover:underline"
                onClick={() => props.onOpenSource(citation.source_id)}
              >
                Показать документ
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2 max-h-[60vh] overflow-auto">
          {props.globalNotes.length === 0 ? (
            <p className="text-sm text-slate-500">
              Нет сохранённых заметок. Нажмите ↳ под ответом чата, чтобы сохранить заметку.
            </p>
          ) : null}
          {props.globalNotes.map((note) => (
            <div key={note.id} className="rounded border border-slate-200 p-2 space-y-1 relative">
              <div className="flex items-start justify-between gap-1">
                <p className="text-xs text-slate-400">
                  {note.source_notebook_title} · {new Date(note.created_at).toLocaleDateString('ru-RU')}
                </p>
                <button
                  type="button"
                  className="shrink-0 text-slate-400 hover:text-red-500 transition-colors text-sm leading-none"
                  title="Удалить заметку"
                  onClick={() => props.onDeleteNote(note)}
                >
                  ✕
                </button>
              </div>
              <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">{note.content}</p>
            </div>
          ))}
        </div>
      )}

    </aside>
  );
}
