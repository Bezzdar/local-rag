'use client';

import { api } from '@/lib/api';
import { CHUNKING_METHOD_LABELS, CHUNKING_METHODS, DOC_TYPE_LABELS, DOC_TYPES, ParsingSettings } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

type Props = {
  notebookId: string;
};

export default function ParsingSettingsPanel({ notebookId }: Props) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ParsingSettings | null>(null);

  const parsingSettings = useQuery({
    queryKey: ['parsing-settings', notebookId],
    queryFn: () => api.getParsingSettings(notebookId),
    enabled: Boolean(notebookId),
  });

  useEffect(() => {
    if (parsingSettings.data) {
      setDraft(parsingSettings.data);
    }
  }, [parsingSettings.data]);

  const updateSettings = useMutation({
    mutationFn: (payload: ParsingSettings) => api.updateParsingSettings(notebookId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['parsing-settings', notebookId] }),
  });

  if (parsingSettings.isLoading) {
    return <p className="text-xs text-slate-500">Загрузка настроек парсинга…</p>;
  }

  if (parsingSettings.isError || !parsingSettings.data) {
    return <p className="text-xs text-red-600">Не удалось загрузить настройки парсинга.</p>;
  }

  const method = draft?.chunking_method ?? 'general';

  const set = <K extends keyof ParsingSettings>(key: K, value: ParsingSettings[K]) =>
    setDraft((prev) => ({ ...(prev ?? parsingSettings.data), [key]: value }));

  return (
    <div className="space-y-2">
      {/* Chunking method selector */}
      <label className="text-xs block">
        Метод чанкинга
        <select
          className="mt-1 w-full rounded border p-1 text-xs"
          value={method}
          onChange={(e) => set('chunking_method', e.target.value)}
        >
          {CHUNKING_METHODS.map((m) => (
            <option key={m} value={m}>{CHUNKING_METHOD_LABELS[m]}</option>
          ))}
        </select>
      </label>

      {/* General & Context Enrichment: chunk_size + overlap */}
      {(method === 'general' || method === 'context_enrichment') && (
        <>
          <label className="text-xs block">
            Chunk size
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.chunk_size ?? 512}
              onChange={(e) => set('chunk_size', Number(e.target.value))}
              type="number"
              min={1}
            />
          </label>
          <label className="text-xs block">
            Chunk overlap
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.chunk_overlap ?? 64}
              onChange={(e) => set('chunk_overlap', Number(e.target.value))}
              type="number"
              min={0}
            />
          </label>
        </>
      )}

      {/* Context Enrichment: context_window + use_llm_summary */}
      {method === 'context_enrichment' && (
        <>
          <label className="text-xs block">
            Context window (символов)
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.context_window ?? 128}
              onChange={(e) => set('context_window', Number(e.target.value))}
              type="number"
              min={0}
            />
          </label>
          <label className="text-xs inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={draft?.use_llm_summary ?? false}
              onChange={(e) => set('use_llm_summary', e.target.checked)}
            />
            Использовать LLM-суммаризацию контекста
          </label>
        </>
      )}

      {/* Hierarchy: doc_type + fallback chunk_size */}
      {method === 'hierarchy' && (
        <>
          <label className="text-xs block">
            Тип документа
            <select
              className="mt-1 w-full rounded border p-1 text-xs"
              value={draft?.doc_type ?? 'technical_manual'}
              onChange={(e) => set('doc_type', e.target.value)}
            >
              {DOC_TYPES.map((t) => (
                <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </label>
          <label className="text-xs block">
            Размер чанка (fallback)
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.chunk_size ?? 512}
              onChange={(e) => set('chunk_size', Number(e.target.value))}
              type="number"
              min={1}
            />
          </label>
        </>
      )}

      {/* PCR: parent_chunk_size + child_chunk_size */}
      {method === 'pcr' && (
        <>
          <label className="text-xs block">
            Parent chunk size (токенов)
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.parent_chunk_size ?? 1024}
              onChange={(e) => set('parent_chunk_size', Number(e.target.value))}
              type="number"
              min={64}
            />
          </label>
          <label className="text-xs block">
            Child chunk size (токенов)
            <input
              className="mt-1 w-full rounded border p-1"
              value={draft?.child_chunk_size ?? 128}
              onChange={(e) => set('child_chunk_size', Number(e.target.value))}
              type="number"
              min={16}
            />
          </label>
        </>
      )}

      {/* Symbol: separator */}
      {method === 'symbol' && (
        <label className="text-xs block">
          Символ-разделитель
          <input
            className="mt-1 w-full rounded border p-1 font-mono"
            value={draft?.symbol_separator ?? '---chunk---'}
            onChange={(e) => set('symbol_separator', e.target.value)}
            placeholder="---chunk---"
          />
        </label>
      )}

      {/* OCR settings — always shown */}
      <div className="pt-1 border-t border-slate-100 space-y-2">
        <p className="text-xs text-slate-500 font-medium">OCR</p>
        <label className="text-xs block">
          Язык OCR
          <input
            className="mt-1 w-full rounded border p-1"
            value={draft?.ocr_language ?? 'rus+eng'}
            onChange={(e) => set('ocr_language', e.target.value)}
          />
        </label>
        <label className="text-xs inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={draft?.ocr_enabled ?? true}
            onChange={(e) => set('ocr_enabled', e.target.checked)}
          />
          OCR включён
        </label>
        <label className="text-xs inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={draft?.auto_parse_on_upload ?? false}
            onChange={(e) => set('auto_parse_on_upload', e.target.checked)}
          />
          Авто-парсинг при загрузке
        </label>
      </div>

      <button
        type="button"
        className="rounded border border-slate-300 px-2 py-1 text-xs"
        onClick={() => draft && updateSettings.mutate(draft)}
        disabled={updateSettings.isPending}
      >
        Сохранить глобальные
      </button>
    </div>
  );
}
