import { z } from 'zod';
import { ChatMessageSchema, CitationSchema, NoteSchema, NotebookSchema, SourceSchema } from '@/types/dto';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

async function request<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, cache: 'no-store' });
  if (!res.ok) throw new Error(await res.text());
  return schema.parse(await res.json());
}

export const api = {
  listNotebooks: () => request('/api/notebooks', { method: 'GET' }, z.array(NotebookSchema)),
  createNotebook: (title: string) => request('/api/notebooks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) }, NotebookSchema),
  listSources: (notebookId: string) => request(`/api/notebooks/${notebookId}/sources`, { method: 'GET' }, z.array(SourceSchema)),
  uploadSource: async (notebookId: string, file: File) => {
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch(`${API_BASE}/api/notebooks/${notebookId}/sources/upload`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    return SourceSchema.parse(await res.json());
  },
  listMessages: (notebookId: string) => request(`/api/notebooks/${notebookId}/messages`, { method: 'GET' }, z.array(ChatMessageSchema)),
  listNotes: (notebookId: string) => request(`/api/notebooks/${notebookId}/notes`, { method: 'GET' }, z.array(NoteSchema)),
  createNote: (notebookId: string, title: string, content: string) => request(`/api/notebooks/${notebookId}/notes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content }) }, NoteSchema),
  getFileUrl: (path: string) => `${API_BASE}/api/files?path=${encodeURIComponent(path)}`,
};

export const CitationsSchema = z.array(CitationSchema);
