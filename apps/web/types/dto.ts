import { z } from 'zod';

export const NotebookSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const SourceSchema = z.object({
  id: z.string(),
  notebook_id: z.string(),
  filename: z.string(),
  file_path: z.string(),
  file_type: z.enum(['pdf', 'docx', 'xlsx', 'other']),
  size_bytes: z.number(),
  status: z.enum(['new', 'indexing', 'indexed', 'failed']),
  added_at: z.string(),
  is_enabled: z.boolean().optional(),
  has_docs: z.boolean().optional(),
  has_parsing: z.boolean().optional(),
  has_base: z.boolean().optional(),
  sort_order: z.number().default(0),
  individual_config: z
    .object({
      chunk_size: z.number().nullable(),
      chunk_overlap: z.number().nullable(),
      ocr_enabled: z.boolean().nullable(),
      ocr_language: z.string().nullable(),
    })
    .optional(),
});

export const ChatMessageSchema = z.object({
  id: z.string(),
  notebook_id: z.string(),
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  created_at: z.string(),
});

export const CitationSchema = z.object({
  id: z.string(),
  notebook_id: z.string(),
  source_id: z.string(),
  filename: z.string(),
  location: z.object({
    page: z.number().nullish(),
    sheet: z.string().nullish(),
    paragraph: z.number().nullish(),
  }),
  snippet: z.string(),
  score: z.number(),
  doc_order: z.number().default(0),
});

export const SavedCitationSchema = z.object({
  id: z.string(),
  notebook_id: z.string(),
  source_id: z.string(),
  filename: z.string(),
  doc_order: z.number(),
  chunk_text: z.string(),
  location: z.object({
    page: z.number().nullish(),
    sheet: z.string().nullish(),
    paragraph: z.number().nullish(),
  }),
  created_at: z.string(),
  source_notebook_id: z.string(),
  source_type: z.string().default('notebook'),
});

export const GlobalNoteSchema = z.object({
  id: z.string(),
  content: z.string(),
  source_notebook_id: z.string(),
  source_notebook_title: z.string(),
  created_at: z.string(),
  source_refs: z.array(z.record(z.union([z.string(), z.number()]))).default([]),
});

export const NoteSchema = z.object({
  id: z.string(),
  notebook_id: z.string(),
  title: z.string(),
  content: z.string(),
  created_at: z.string(),
});

export type Notebook = z.infer<typeof NotebookSchema>;
export type Source = z.infer<typeof SourceSchema>;
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type Citation = z.infer<typeof CitationSchema>;
export type SavedCitation = z.infer<typeof SavedCitationSchema>;
export type GlobalNote = z.infer<typeof GlobalNoteSchema>;
export type Note = z.infer<typeof NoteSchema>;


export const AgentManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.string(),
  requires: z.array(z.string()).optional(),
});

export type AgentManifest = z.infer<typeof AgentManifestSchema>;

export const ParsingSettingsSchema = z.object({
  chunk_size: z.number(),
  chunk_overlap: z.number(),
  min_chunk_size: z.number(),
  ocr_enabled: z.boolean(),
  ocr_language: z.string(),
  auto_parse_on_upload: z.boolean().default(false),
});

export type ParsingSettings = z.infer<typeof ParsingSettingsSchema>;
