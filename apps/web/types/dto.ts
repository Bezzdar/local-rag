import { z } from 'zod';

export const NotebookSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const IndividualConfigSchema = z.object({
  chunk_size: z.number().nullable().optional(),
  chunk_overlap: z.number().nullable().optional(),
  ocr_enabled: z.boolean().nullable().optional(),
  ocr_language: z.string().nullable().optional(),
  chunking_method: z.string().nullable().optional(),
  context_window: z.number().nullable().optional(),
  use_llm_summary: z.boolean().nullable().optional(),
  doc_type: z.string().nullable().optional(),
  parent_chunk_size: z.number().nullable().optional(),
  child_chunk_size: z.number().nullable().optional(),
  symbol_separator: z.string().nullable().optional(),
});

export type IndividualConfig = z.infer<typeof IndividualConfigSchema>;

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
  individual_config: IndividualConfigSchema.optional(),
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

export type Notebook = z.infer<typeof NotebookSchema>;
export type Source = z.infer<typeof SourceSchema>;
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type Citation = z.infer<typeof CitationSchema>;
export type SavedCitation = z.infer<typeof SavedCitationSchema>;
export type GlobalNote = z.infer<typeof GlobalNoteSchema>;


export const AgentManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.string(),
  requires: z.array(z.string()).optional(),
});

export type AgentManifest = z.infer<typeof AgentManifestSchema>;

export const CHUNKING_METHODS = ['general', 'context_enrichment', 'hierarchy', 'pcr', 'symbol'] as const;
export type ChunkingMethod = typeof CHUNKING_METHODS[number];

export const DOC_TYPES = ['technical_manual', 'gost', 'api_docs', 'markdown'] as const;
export type DocType = typeof DOC_TYPES[number];

export const CHUNKING_METHOD_LABELS: Record<ChunkingMethod, string> = {
  general: 'General',
  context_enrichment: 'Context Enrichment',
  hierarchy: 'Hierarchy',
  pcr: 'PCR',
  symbol: 'Symbol',
};

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  technical_manual: 'Technical Manual',
  gost: 'GOST',
  api_docs: 'API Docs',
  markdown: 'Markdown',
};

export const ParsingSettingsSchema = z.object({
  chunk_size: z.number(),
  chunk_overlap: z.number(),
  min_chunk_size: z.number(),
  ocr_enabled: z.boolean(),
  ocr_language: z.string(),
  auto_parse_on_upload: z.boolean().default(false),
  chunking_method: z.string().default('general'),
  context_window: z.number().default(128),
  use_llm_summary: z.boolean().default(false),
  doc_type: z.string().default('technical_manual'),
  parent_chunk_size: z.number().default(1024),
  child_chunk_size: z.number().default(128),
  symbol_separator: z.string().default('---chunk---'),
});

export type ParsingSettings = z.infer<typeof ParsingSettingsSchema>;
