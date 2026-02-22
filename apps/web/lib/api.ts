import { z } from 'zod';
import { AgentManifestSchema, ChatMessageSchema, CitationSchema, GlobalNoteSchema, IndividualConfig, NoteSchema, NotebookSchema, ParsingSettings, ParsingSettingsSchema, SavedCitationSchema, SourceSchema } from '@/types/dto';

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
  renameNotebook: (notebookId: string, title: string) =>
    request(
      `/api/notebooks/${notebookId}`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) },
      NotebookSchema,
    ),
  duplicateNotebook: (notebookId: string) =>
    request(`/api/notebooks/${notebookId}/duplicate`, { method: 'POST' }, NotebookSchema),
  deleteNotebook: async (notebookId: string) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  listSources: (notebookId: string) => request(`/api/notebooks/${notebookId}/sources`, { method: 'GET' }, z.array(SourceSchema)),
  getParsingSettings: (notebookId: string) =>
    request(
      `/api/notebooks/${notebookId}/parsing-settings`,
      { method: 'GET' },
      ParsingSettingsSchema,
    ),
  updateParsingSettings: (
    notebookId: string,
    payload: ParsingSettings,
  ) =>
    request(
      `/api/notebooks/${notebookId}/parsing-settings`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
      ParsingSettingsSchema,
    ),
  deleteSource: async (sourceId: string) => {
    const response = await fetch(`${apiBase}/api/sources/${sourceId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  reparseSource: (sourceId: string) =>
    request(`/api/sources/${sourceId}/reparse`, { method: 'POST' }, SourceSchema),
  eraseSource: async (sourceId: string) => {
    const response = await fetch(`${apiBase}/api/sources/${sourceId}/erase`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  updateSource: (
    sourceId: string,
    payload: {
      is_enabled?: boolean;
      individual_config?: IndividualConfig;
    },
  ) =>
    request(
      `/api/sources/${sourceId}`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
      SourceSchema,
    ),
  openSource: async (sourceId: string) => {
    const response = await fetch(`${apiBase}/api/sources/${sourceId}/open`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  reorderSources: async (notebookId: string, orderedIds: string[]) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/sources/reorder`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordered_ids: orderedIds }),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  deleteAllSourceFiles: async (notebookId: string) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/sources/files`, { method: 'DELETE' });
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
  // Saved Citations (persistent, per-notebook)
  listSavedCitations: (notebookId: string) =>
    request(`/api/notebooks/${notebookId}/saved-citations`, { method: 'GET' }, z.array(SavedCitationSchema)),
  saveCitation: (
    notebookId: string,
    payload: {
      source_id: string;
      filename: string;
      doc_order: number;
      chunk_text: string;
      page?: number | null;
      sheet?: string | null;
      source_notebook_id: string;
      source_type?: string;
    },
  ) =>
    request(
      `/api/notebooks/${notebookId}/saved-citations`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
      SavedCitationSchema,
    ),
  deleteSavedCitation: async (notebookId: string, citationId: string) => {
    const response = await fetch(`${apiBase}/api/notebooks/${notebookId}/saved-citations/${citationId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  // Global Notes (persistent, cross-notebook)
  listGlobalNotes: () => request('/api/notes', { method: 'GET' }, z.array(GlobalNoteSchema)),
  createGlobalNote: (payload: {
    content: string;
    source_notebook_id: string;
    source_notebook_title: string;
    source_refs?: Record<string, string | number>[];
  }) =>
    request(
      '/api/notes',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
      GlobalNoteSchema,
    ),
  deleteGlobalNote: async (noteId: string) => {
    const response = await fetch(`${apiBase}/api/notes/${noteId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
  },
  listAgents: () => request('/api/agents', { method: 'GET' }, z.array(AgentManifestSchema)),
  fileUrl: (path: string) => `${apiBase}/api/files?path=${encodeURIComponent(path)}`,
};

export const CitationsSchema = z.array(CitationSchema);
