import { z } from 'zod';
import { ChatMessageSchema, CitationSchema, NoteSchema, NotebookSchema, SourceSchema } from '@/types/dto';
import { getRuntimeConfig } from '@/lib/runtime-config';

async function request<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  const { apiBase } = getRuntimeConfig();
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
  listSources: (notebookId: string) => request(`/api/notebooks/${notebookId}/sources`, { method: 'GET' }, z.array(SourceSchema)),
  uploadSource: async (notebookId: string, file: File) => {
    const { apiBase } = getRuntimeConfig();
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/sources/upload`, { method: 'POST', body: form });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return SourceSchema.parse(await response.json());
  },
  listMessages: (notebookId: string) => request(`/api/notebooks/${notebookId}/messages`, { method: 'GET' }, z.array(ChatMessageSchema)),
  listNotes: (notebookId: string) => request(`/api/notebooks/${notebookId}/notes`, { method: 'GET' }, z.array(NoteSchema)),
  createNote: (notebookId: string, title: string, content: string) =>
    request(
      `/api/notebooks/${notebookId}/notes`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content }) },
      NoteSchema,
    ),
  fileUrl: (path: string) => {
    const { apiBase } = getRuntimeConfig();
    return `${apiBase}/api/files?path=${encodeURIComponent(path)}`;
  },
};

export const CitationsSchema = z.array(CitationSchema);
