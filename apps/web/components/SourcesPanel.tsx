'use client';

import { Notebook, Source } from '@/types/dto';
import Link from 'next/link';
import { useMemo, useState } from 'react';

type Props = {
  notebooks: Notebook[];
  activeNotebookId: string;
  sources: Source[];
  selectedSourceIds: string[];
  onNotebookChange: (id: string) => void;
  onToggleSource: (sourceId: string) => void;
  onSelectAllSources: () => void;
  onClearSourceSelection: () => void;
  onDeleteAllSources: () => void;
  onDeleteUnselectedSources: () => void;
  onUpload: (file: File) => void;
};

export default function SourcesPanel(props: Props) {
  const [search, setSearch] = useState('');

  const visibleSources = useMemo(
    () => props.sources.filter((source) => source.filename.toLowerCase().includes(search.toLowerCase())),
    [props.sources, search],
  );

  return (
    <aside className="w-full h-full border-r border-slate-200 bg-white p-4 space-y-4">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Notebooks</p>
        <select
          className="w-full rounded border border-slate-300 p-2 text-sm"
          value={props.activeNotebookId}
          onChange={(event) => props.onNotebookChange(event.target.value)}
        >
          {props.notebooks.map((notebook) => (
            <option key={notebook.id} value={notebook.id}>{notebook.title}</option>
          ))}
        </select>
      </div>

      <Link
        href="/notebooks"
        className="block rounded border border-slate-300 p-2 text-center text-sm text-slate-700 hover:bg-slate-50"
      >
        На главную страницу
      </Link>

      <div className="space-y-2">
        <input
          className="w-full rounded border border-slate-300 p-2 text-sm"
          placeholder="Search sources"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />

        <label className="block rounded border border-dashed border-slate-300 p-3 text-sm text-slate-600 cursor-pointer">
          Upload PDF/DOCX/XLSX
          <input
            type="file"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                props.onUpload(file);
              }
            }}
          />
        </label>
      </div>

      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={props.onSelectAllSources}>
            Выделить все
          </button>
          <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={props.onClearSourceSelection}>
            Снять выделение
          </button>
          <button
            type="button"
            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600"
            onClick={props.onDeleteAllSources}
          >
            Удалить все
          </button>
          <button
            type="button"
            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600"
            onClick={props.onDeleteUnselectedSources}
          >
            Удалить невыбранные
          </button>
        </div>
      </div>

      <div className="space-y-2 max-h-[55vh] overflow-auto">
        {visibleSources.length === 0 ? <p className="text-sm text-slate-500">Нет источников</p> : null}
        {visibleSources.map((source) => (
          <label key={source.id} className="flex gap-2 rounded border border-slate-200 p-2">
            <input
              type="checkbox"
              checked={props.selectedSourceIds.includes(source.id)}
              onChange={() => props.onToggleSource(source.id)}
            />
            <div>
              <p className="text-sm font-medium break-all">{source.filename}</p>
              <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-xs">{source.status}</span>
            </div>
          </label>
        ))}
      </div>
    </aside>
  );
}
