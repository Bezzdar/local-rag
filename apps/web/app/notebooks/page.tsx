'use client';

import ConnectionIndicator from '@/components/ConnectionIndicator';
import RuntimeSettings from '@/components/RuntimeSettings';
import { api } from '@/lib/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

export default function NotebooksPage() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(true);
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

  if (notebooks.isLoading) {
    return <div className="p-6">Loading notebooks...</div>;
  }
  if (notebooks.isError) {
    return <div className="p-6">Failed to load notebooks.</div>;
  }

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
              onClick={() => createNotebook.mutate(`Notebook ${new Date().toLocaleTimeString()}`)}
            >
              New notebook
            </button>
          </div>

          {notebooks.data?.length === 0 ? <div className="rounded border bg-white p-4 text-sm text-slate-500">Нет ноутбуков.</div> : null}

          <div className="space-y-2">
            {notebooks.data?.map((notebook) => (
              <div key={notebook.id} className="rounded border bg-white p-3">
                <div className="flex items-start justify-between gap-3">
                  <Link href={`/notebooks/${notebook.id}`} className="block flex-1 hover:text-slate-700">
                    <div className="font-medium">{notebook.title}</div>
                    <div className="text-xs text-slate-500">{new Date(notebook.updated_at).toLocaleString()}</div>
                  </Link>
                  <button
                    type="button"
                    className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => deleteNotebook.mutate(notebook.id)}
                    disabled={deleteNotebook.isPending}
                  >
                    Удалить
                  </button>
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
          {isSettingsOpen ? <RuntimeSettings /> : null}
        </aside>
      </div>
    </div>
  );
}
