'use client';

import { Notebook, Source } from '@/types/dto';
import { useMemo, useState } from 'react';

type Props = {
  notebooks: Notebook[];
  activeNotebookId: string;
  sources: Source[];
  selectedSourceIds: string[];
  onNotebookChange: (id: string) => void;
  onCreateNotebook: (title: string) => void;
  onToggleSource: (sourceId: string) => void;
  onUpload: (file: File) => void;
};

export default function SourcesPanel(props: Props) {
  const [newTitle, setNewTitle] = useState('');
  const [search, setSearch] = useState('');

  const visibleSources = useMemo(
    () => props.sources.filter((source) => source.filename.toLowerCase().includes(search.toLowerCase())),
    [props.sources, search],
  );

  return (
    <aside className="w-full lg:w-80 border-r border-slate-200 bg-white p-4 space-y-4">
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

      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 p-2 text-sm"
          placeholder="New notebook"
          value={newTitle}
          onChange={(event) => setNewTitle(event.target.value)}
        />
        <button
          className="rounded bg-slate-900 px-3 text-white"
          onClick={() => {
            const title = newTitle.trim();
            if (!title) {
              return;
            }
            props.onCreateNotebook(title);
            setNewTitle('');
          }}
        >
          +
        </button>
      </div>

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
