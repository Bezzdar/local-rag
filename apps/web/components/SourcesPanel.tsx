'use client';

import { Notebook, Source } from '@/types/dto';
import Link from 'next/link';
import { useMemo, useRef, useState } from 'react';

type Props = {
  notebooks: Notebook[];
  activeNotebookId: string;
  sources: Source[];
  selectedSourceIds: string[];
  onNotebookChange: (id: string) => void;
  onToggleSource: (sourceId: string) => void;
  onSelectAllSources: () => void;
  onClearSourceSelection: () => void;
  onDeleteSelectedSources: () => void;
  onDeleteUnselectedSources: () => void;
  onParseAllSources: () => void;
  onParseSelectedSources: () => void;
  onUpload: (file: File) => void;
  onEraseSource: (source: Source) => void;
  onOpenConfig: (source: Source) => void;
  onDeleteSource: (source: Source) => void;
  onParseSource: (source: Source) => void;
  onOpenSource: (source: Source) => void;
  onReorderSources: (orderedIds: string[]) => void;
};

function Lamp({ label, active }: { label: string; active: boolean }) {
  return <span className={`font-semibold ${active ? 'text-emerald-600' : 'text-slate-400'}`}>{label}</span>;
}

export default function SourcesPanel(props: Props) {
  const [search, setSearch] = useState('');
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const dragSourceId = useRef<string | null>(null);

  // Sort sources by sort_order for display
  const sortedSources = useMemo(
    () => [...props.sources].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)),
    [props.sources],
  );

  // Build sequential display numbers (1-based position in sorted list)
  const docNumbers = useMemo(() => {
    const map: Record<string, number> = {};
    sortedSources.forEach((s, idx) => { map[s.id] = idx + 1; });
    return map;
  }, [sortedSources]);

  const visibleSources = useMemo(
    () => sortedSources.filter((source) => source.filename.toLowerCase().includes(search.toLowerCase())),
    [sortedSources, search],
  );

  // Drag-and-drop handlers
  const handleDragStart = (e: React.DragEvent, sourceId: string) => {
    dragSourceId.current = sourceId;
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverId(targetId);
  };

  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    setDragOverId(null);
    const fromId = dragSourceId.current;
    if (!fromId || fromId === targetId) return;

    // Reorder: move fromId to the position of targetId
    const currentOrder = sortedSources.map((s) => s.id);
    const fromIdx = currentOrder.indexOf(fromId);
    const toIdx = currentOrder.indexOf(targetId);
    if (fromIdx === -1 || toIdx === -1) return;

    const newOrder = [...currentOrder];
    newOrder.splice(fromIdx, 1);
    newOrder.splice(toIdx, 0, fromId);
    props.onReorderSources(newOrder);
    dragSourceId.current = null;
  };

  const handleDragEnd = () => {
    setDragOverId(null);
    dragSourceId.current = null;
  };

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
        {/* Row 1: Select / Deselect */}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={props.onSelectAllSources}>
            Выделить все
          </button>
          <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={props.onClearSourceSelection}>
            Снять выделение
          </button>
        </div>

        {/* Row 2: Parse buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className="rounded border border-blue-200 px-2 py-1 text-xs text-blue-700"
            onClick={props.onParseAllSources}
          >
            Парсить все
          </button>
          <button
            type="button"
            className="rounded border border-blue-200 px-2 py-1 text-xs text-blue-700"
            onClick={props.onParseSelectedSources}
          >
            Парсить выбранное
          </button>
        </div>

        {/* Row 3: Delete buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600"
            onClick={props.onDeleteSelectedSources}
          >
            Удалить выбранное
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
        {visibleSources.map((source) => {
          const docNum = docNumbers[source.id] ?? 0;
          const isDragOver = dragOverId === source.id;
          return (
            <div
              key={source.id}
              className={`rounded border p-2 cursor-grab active:cursor-grabbing transition-colors ${isDragOver ? 'border-blue-400 bg-blue-50' : 'border-slate-200'}`}
              draggable
              onDragStart={(e) => handleDragStart(e, source.id)}
              onDragOver={(e) => handleDragOver(e, source.id)}
              onDrop={(e) => handleDrop(e, source.id)}
              onDragEnd={handleDragEnd}
              onDoubleClick={() => props.onOpenSource(source)}
              title="Двойной клик — открыть документ. Перетащите для изменения порядка."
            >
              <div className="flex items-center gap-2 text-sm">
                {/* Sequential document number badge */}
                <span
                  className="shrink-0 inline-flex items-center justify-center w-7 h-5 rounded bg-slate-700 text-white text-xs font-mono font-bold select-none"
                  title={`Документ №${docNum} в ноутбуке`}
                >
                  {docNum}
                </span>
                <input
                  type="checkbox"
                  checked={props.selectedSourceIds.includes(source.id)}
                  onChange={() => props.onToggleSource(source.id)}
                  title="Выбрать источник для чата"
                  onClick={(e) => e.stopPropagation()}
                />
                <p className="min-w-0 flex-1 truncate font-medium" title={source.filename}>{source.filename}</p>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">{source.status}</span>
                <div className="flex gap-2 text-lg leading-none">
                  <Lamp label="d" active={source.has_docs ?? false} />
                  <Lamp label="p" active={source.has_parsing ?? false} />
                  <Lamp label="b" active={source.has_base ?? false} />
                </div>
                {/* Play button: manually start parsing */}
                <button
                  type="button"
                  className="rounded border border-green-300 px-2 text-xs text-green-700"
                  onClick={(e) => { e.stopPropagation(); props.onParseSource(source); }}
                  title="Запустить парсинг документа"
                >
                  ▶
                </button>
                <div className="flex gap-1">
                  <button type="button" className="rounded border px-2 text-xs" onClick={(e) => { e.stopPropagation(); props.onOpenConfig(source); }} title="Настроить парсинг файла">⚙</button>
                  {/* Erase: clear parsing/chunking/DB data (keep source entry) */}
                  <button type="button" className="rounded border border-amber-300 px-2 text-xs text-amber-700" onClick={(e) => { e.stopPropagation(); props.onEraseSource(source); }} title="Стереть parsing/base данные">
                    ✖
                  </button>
                  {/* Delete: remove document row + all data */}
                  <button type="button" className="rounded border border-red-300 px-2 text-xs text-red-600" onClick={(e) => { e.stopPropagation(); props.onDeleteSource(source); }} title="Удалить документ полностью">
                    🗑
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
