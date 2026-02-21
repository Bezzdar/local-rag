'use client';

import { api } from '@/lib/api';
import { ParsingSettings } from '@/types/dto';
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

  return (
    <div className="space-y-2">
      <label className="text-xs block">
        Chunk size
        <input
          className="mt-1 w-full rounded border p-1"
          value={draft?.chunk_size ?? 512}
          onChange={(e) => setDraft((prev) => ({ ...(prev ?? parsingSettings.data), chunk_size: Number(e.target.value) }))}
          type="number"
        />
      </label>
      <label className="text-xs block">
        Chunk overlap
        <input
          className="mt-1 w-full rounded border p-1"
          value={draft?.chunk_overlap ?? 64}
          onChange={(e) => setDraft((prev) => ({ ...(prev ?? parsingSettings.data), chunk_overlap: Number(e.target.value) }))}
          type="number"
        />
      </label>
      <label className="text-xs block">
        OCR language
        <input
          className="mt-1 w-full rounded border p-1"
          value={draft?.ocr_language ?? 'rus+eng'}
          onChange={(e) => setDraft((prev) => ({ ...(prev ?? parsingSettings.data), ocr_language: e.target.value }))}
        />
      </label>
      <label className="text-xs inline-flex items-center gap-2">
        <input
          type="checkbox"
          checked={draft?.ocr_enabled ?? true}
          onChange={(e) => setDraft((prev) => ({ ...(prev ?? parsingSettings.data), ocr_enabled: e.target.checked }))}
        />
        OCR enabled
      </label>
      <label className="text-xs inline-flex items-center gap-2">
        <input
          type="checkbox"
          checked={draft?.auto_parse_on_upload ?? false}
          onChange={(e) => setDraft((prev) => ({ ...(prev ?? parsingSettings.data), auto_parse_on_upload: e.target.checked }))}
        />
        Автоматически парсить при загрузке
      </label>
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
