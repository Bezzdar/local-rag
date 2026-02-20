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
    page: z.number().optional(),
    sheet: z.string().optional(),
    paragraph: z.number().optional(),
  }),
  snippet: z.string(),
  score: z.number(),
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
export type Note = z.infer<typeof NoteSchema>;


export const ParsingSettingsSchema = z.object({
  chunk_size: z.number(),
  chunk_overlap: z.number(),
  min_chunk_size: z.number(),
  ocr_enabled: z.boolean(),
  ocr_language: z.string(),
});

export type ParsingSettings = z.infer<typeof ParsingSettingsSchema>;
