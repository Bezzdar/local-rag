'use client';

import { api } from '@/lib/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';

export default function NotebooksPage() {
  const queryClient = useQueryClient();
  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const createNotebook = useMutation({
    mutationFn: api.createNotebook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notebooks'] }),
  });

  if (notebooks.isLoading) {
    return <div className="p-6">Loading notebooks...</div>;
  }
  if (notebooks.isError) {
    return <div className="p-6">Failed to load notebooks.</div>;
  }

  return (
    <div className="mx-auto max-w-3xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Notebooks</h1>
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
          <Link key={notebook.id} href={`/notebooks/${notebook.id}`} className="block rounded border bg-white p-3 hover:bg-slate-50">
            <div className="font-medium">{notebook.title}</div>
            <div className="text-xs text-slate-500">{new Date(notebook.updated_at).toLocaleString()}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
