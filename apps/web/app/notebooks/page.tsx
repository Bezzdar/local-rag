'use client';

import ConnectionIndicator from '@/components/ConnectionIndicator';
import ParsingSettingsPanel from '@/components/ParsingSettingsPanel';
import RuntimeSettings from '@/components/RuntimeSettings';
import { api } from '@/lib/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

export default function NotebooksPage() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(true);
  const [isRuntimeOpen, setIsRuntimeOpen] = useState(true);
  const [isParsingOpen, setIsParsingOpen] = useState(true);
  const [selectedNotebookId, setSelectedNotebookId] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newNotebookName, setNewNotebookName] = useState('');
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [renamingNotebookId, setRenamingNotebookId] = useState<string | null>(null);
  const [renameNotebookName, setRenameNotebookName] = useState('');
  const queryClient = useQueryClient();
  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const createNotebook = useMutation({
    mutationFn: api.createNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks'] }),
  });
  const deleteNotebook = useMutation({
    mutationFn: api.deleteNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks'] }),
  });
  const renameNotebook = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameNotebook(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks'] }),
  });
  const duplicateNotebook = useMutation({
    mutationFn: api.duplicateNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks'] }),
  });

  function openDialog() {
    setNewNotebookName('');
    setIsDialogOpen(true);
  }

  function handleCreate() {
    const title = newNotebookName.trim() || `Ноутбук ${new Date().toLocaleTimeString()}`;
    createNotebook.mutate(title);
    setIsDialogOpen(false);
  }

  function handleCancel() {
    setIsDialogOpen(false);
  }

  function openRenameDialog(notebookId: string, currentTitle: string) {
    setRenamingNotebookId(notebookId);
    setRenameNotebookName(currentTitle);
    setIsRenameDialogOpen(true);
  }

  function handleRename() {
    if (!renamingNotebookId) return;
    const title = renameNotebookName.trim();
    if (!title) return;
    renameNotebook.mutate({ id: renamingNotebookId, title });
    setIsRenameDialogOpen(false);
    setRenamingNotebookId(null);
  }

  function handleRenameCancel() {
    setIsRenameDialogOpen(false);
    setRenamingNotebookId(null);
  }

  if (notebooks.isLoading) {
    return <div className="p-6">Loading notebooks...</div>;
  }
  if (notebooks.isError) {
    return <div className="p-6">Failed to load notebooks.</div>;
  }

  const activeNotebookId = selectedNotebookId ?? notebooks.data?.[0]?.id;

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold">Notebooks</h1>
              <ConnectionIndicator />
            </div>
            <button
              className="rounded bg-slate-900 px-3 py-2 text-white"
              onClick={openDialog}
            >
              Новый ноутбук
            </button>
          </div>

          {notebooks.data?.length === 0 ? <div className="rounded border bg-white p-4 text-sm text-slate-500">Нет ноутбуков.</div> : null}

          <div className="space-y-2">
            {notebooks.data?.map((notebook) => (
              <div
                key={notebook.id}
                className={`rounded border bg-white p-3 ${activeNotebookId === notebook.id ? 'border-slate-400' : ''}`}
                onClick={() => setSelectedNotebookId(notebook.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <Link href={`/notebooks/${notebook.id}`} className="block flex-1 hover:text-slate-700">
                    <div className="font-medium">{notebook.title}</div>
                    <div className="text-xs text-slate-500">{new Date(notebook.updated_at).toLocaleString()}</div>
                  </Link>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={(e) => { e.stopPropagation(); openRenameDialog(notebook.id, notebook.title); }}
                      disabled={renameNotebook.isPending}
                    >
                      Переименовать
                    </button>
                    <button
                      type="button"
                      className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={(e) => { e.stopPropagation(); duplicateNotebook.mutate(notebook.id); }}
                      disabled={duplicateNotebook.isPending}
                    >
                      Дублировать
                    </button>
                    <button
                      type="button"
                      className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={(e) => { e.stopPropagation(); deleteNotebook.mutate(notebook.id); }}
                      disabled={deleteNotebook.isPending}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <aside className={`sticky top-3 shrink-0 rounded border border-slate-200 bg-white p-2 transition-all ${isSettingsOpen ? 'w-[360px]' : 'w-12'}`}>
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
              onClick={() => setIsSettingsOpen((current) => !current)}
              aria-label={isSettingsOpen ? 'Свернуть панель настроек' : 'Развернуть панель настроек'}
            >
              {isSettingsOpen ? '→' : '←'}
            </button>
          </div>
          {isSettingsOpen ? (
            <div className="space-y-2">
              <section className="rounded border border-slate-200 p-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left text-sm font-semibold"
                  onClick={() => setIsRuntimeOpen((current) => !current)}
                >
                  Провайдер LLM
                  <span>{isRuntimeOpen ? '−' : '+'}</span>
                </button>
                {isRuntimeOpen ? <div className="mt-2"><RuntimeSettings /></div> : null}
              </section>

              <section className="rounded border border-slate-200 p-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left text-sm font-semibold"
                  onClick={() => setIsParsingOpen((current) => !current)}
                >
                  Глобальные настройки парсинга
                  <span>{isParsingOpen ? '−' : '+'}</span>
                </button>
                {isParsingOpen && activeNotebookId ? <div className="mt-2"><ParsingSettingsPanel notebookId={activeNotebookId} /></div> : null}
              </section>
            </div>
          ) : null}
        </aside>
      </div>

      {isDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded border bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-base font-semibold">Новый ноутбук</h2>
            <input
              type="text"
              className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              placeholder="Название ноутбука"
              value={newNotebookName}
              onChange={(e) => setNewNotebookName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') handleCancel(); }}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                onClick={handleCancel}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700"
                onClick={handleCreate}
              >
                Принять
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {isRenameDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded border bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-base font-semibold">Переименовать ноутбук</h2>
            <input
              type="text"
              className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              placeholder="Название ноутбука"
              value={renameNotebookName}
              onChange={(e) => setRenameNotebookName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') handleRenameCancel(); }}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                onClick={handleRenameCancel}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700"
                onClick={handleRename}
                disabled={!renameNotebookName.trim()}
              >
                Переименовать
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
