import { z } from 'zod';
import { ChatMessageSchema, CitationSchema, NoteSchema, NotebookSchema, SourceSchema } from '@/types/dto';

const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '');

async function request<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...init, cache: 'no-store' });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return schema.parse(await response.json());
}

export const api = {
  listNotebooks: () => request('/api/notebooks', { method: 'GET' }, z.array(NotebookSchema)),
  createNotebook: (title: string) =>
    request(
      '/api/notebooks',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) },
      NotebookSchema,
    ),
  deleteNotebook: async (notebookId: string) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  listSources: (notebookId: string) => request(`/api/notebooks/${notebookId}/sources`, { method: 'GET' }, z.array(SourceSchema)),
  deleteSource: async (sourceId: string) => {
    const response = await fetch(`${apiBase}/api/sources/${sourceId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  uploadSource: async (notebookId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/sources/upload`, { method: 'POST', body: form });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return SourceSchema.parse(await response.json());
  },
  listMessages: (notebookId: string) => request(`/api/notebooks/${notebookId}/messages`, { method: 'GET' }, z.array(ChatMessageSchema)),
  clearMessages: async (notebookId: string) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/messages`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  listNotes: (notebookId: string) => request(`/api/notebooks/${notebookId}/notes`, { method: 'GET' }, z.array(NoteSchema)),
  createNote: (notebookId: string, title: string, content: string) =>
    request(
      `/api/notebooks/${notebookId}/notes`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content }) },
      NoteSchema,
    ),
  fileUrl: (path: string) => `${apiBase}/api/files?path=${encodeURIComponent(path)}`,
};

export const CitationsSchema = z.array(CitationSchema);
