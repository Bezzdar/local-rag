'use client';

import { api } from '@/lib/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';

export default function NotebooksPage() {
  const qc = useQueryClient();
  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const createNotebook = useMutation({ mutationFn: api.createNotebook, onSuccess: () => qc.invalidateQueries({ queryKey: ['notebooks'] }) });

  if (notebooks.isLoading) return <div className="p-6">Loading...</div>;
  if (notebooks.isError) return <div className="p-6">Error loading notebooks</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Notebooks</h1>
      <button className="px-3 py-2 rounded bg-slate-900 text-white" onClick={() => createNotebook.mutate(`Notebook ${Date.now()}`)}>New notebook</button>
      <div className="space-y-2">
        {notebooks.data?.map((n) => <Link key={n.id} href={`/notebooks/${n.id}`} className="block border rounded p-3 bg-white">{n.title}</Link>)}
      </div>
    </div>
  );
}
