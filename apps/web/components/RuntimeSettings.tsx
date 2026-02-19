'use client';

import { getDefaultOllamaBase, getRuntimeConfig, LlmProvider, RuntimeConfig, setRuntimeConfig } from '@/lib/runtime-config';
import { useEffect, useState } from 'react';

const DRAFT_STORAGE_KEY = 'rag.runtime-config.draft';
const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '');

type RuntimeDraft = {
  llmBase: string;
  provider: LlmProvider;
  model: string;
  maxHistory: number;
  debugModelMode: boolean;
};

function getInitialDraft(): RuntimeDraft {
  const runtime = getRuntimeConfig();

  if (typeof window === 'undefined') {
    return {
      llmBase: runtime.llmBase || getDefaultOllamaBase(),
      provider: runtime.llmProvider,
      model: runtime.llmModel,
      maxHistory: runtime.maxHistory,
      debugModelMode: runtime.debugModelMode,
    };
  }

  const raw = window.localStorage.getItem(DRAFT_STORAGE_KEY);
  if (!raw) {
    return {
      llmBase: runtime.llmBase || getDefaultOllamaBase(),
      provider: runtime.llmProvider,
      model: runtime.llmModel,
      maxHistory: runtime.maxHistory,
      debugModelMode: runtime.debugModelMode,
    };
  }

  try {
    const parsed = JSON.parse(raw) as Partial<RuntimeDraft>;
    return {
      llmBase: (parsed.llmBase ?? runtime.llmBase ?? getDefaultOllamaBase()).trim(),
      provider: parsed.provider === 'ollama' || parsed.provider === 'openai' ? parsed.provider : 'none',
      model: (parsed.model ?? runtime.llmModel).trim(),
      maxHistory: Math.min(50, Math.max(1, Number(parsed.maxHistory ?? runtime.maxHistory) || runtime.maxHistory)),
      debugModelMode: Boolean(parsed.debugModelMode ?? runtime.debugModelMode),
    };
  } catch {
    return {
      llmBase: runtime.llmBase || getDefaultOllamaBase(),
      provider: runtime.llmProvider,
      model: runtime.llmModel,
      maxHistory: runtime.maxHistory,
      debugModelMode: runtime.debugModelMode,
    };
  }
}

export default function RuntimeSettings() {
  const [runtime, setRuntime] = useState<RuntimeConfig>(() => getRuntimeConfig());
  const [draft, setDraft] = useState<RuntimeDraft>(() => getInitialDraft());
  const [acceptedBase, setAcceptedBase] = useState(draft.llmBase.trim());
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState('');
  const [info, setInfo] = useState('');

  useEffect(() => {
    const listener = (event: Event) => {
      const customEvent = event as CustomEvent<RuntimeConfig>;
      if (customEvent.detail) {
        setRuntime(customEvent.detail);
      }
    };

    window.addEventListener('rag-runtime-config-changed', listener);
    return () => window.removeEventListener('rag-runtime-config-changed', listener);
  }, []);

  const saveDraft = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
    }
    setInfo('Конфигурация сохранена.');
  };

  const acceptPort = () => {
    const normalized = draft.llmBase.trim();
    setAcceptedBase(normalized);
    if (!normalized) {
      setDraft((current) => ({ ...current, provider: 'none', model: '' }));
      setModels([]);
      setModelsError('');
      setInfo('Поле порта пустое: включен режим None.');
      return;
    }
    setInfo('Порт принят. Теперь выберите поставщика и модель.');
  };

  useEffect(() => {
    const loadModels = async () => {
      if (draft.provider !== 'ollama' || !acceptedBase) {
        setModels([]);
        setModelsError('');
        return;
      }

      setLoadingModels(true);
      setModelsError('');
      try {
        const search = new URLSearchParams({ provider: 'ollama', base_url: acceptedBase });
        const response = await fetch(`${apiBase}/api/llm/models?${search.toString()}`, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as string[];
        setModels(payload);
        setDraft((current) => ({
          ...current,
          model: payload.includes(current.model) ? current.model : payload[0] ?? '',
        }));
      } catch (error) {
        setModels([]);
        setModelsError(error instanceof Error ? error.message : 'Не удалось загрузить модели');
      } finally {
        setLoadingModels(false);
      }
    };

    loadModels();
  }, [acceptedBase, draft.provider]);

  const connect = () => {
    if (draft.provider === 'none' || !acceptedBase) {
      const next = setRuntimeConfig({
        llmBase: draft.llmBase,
        llmProvider: 'none',
        llmModel: '',
        maxHistory: draft.maxHistory,
        debugModelMode: draft.debugModelMode,
      });
      setRuntime(next);
      setInfo('Режим None активирован.');
      return;
    }

    if (!draft.model) {
      setInfo('Сначала выберите модель для подключения.');
      return;
    }

    const next = setRuntimeConfig({
      llmBase: acceptedBase,
      llmProvider: draft.provider,
      llmModel: draft.model,
      maxHistory: draft.maxHistory,
      debugModelMode: draft.debugModelMode,
    });
    setRuntime(next);
    setInfo(`Подключено: Ollama / ${draft.model}.`);
  };

  const disconnect = () => {
    const next = setRuntimeConfig({
      llmBase: draft.llmBase,
      llmProvider: 'none',
      llmModel: '',
      maxHistory: draft.maxHistory,
      debugModelMode: draft.debugModelMode,
    });
    setRuntime(next);
    setInfo('Отключено. Режим None.');
  };

  return (
    <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
      <p className="font-medium text-slate-900">Настройки подключения LLM</p>
      <p className="mt-1 text-[11px] text-slate-500">
        Текущий режим: <span className="font-semibold text-slate-700">{runtime.llmProvider === 'none' ? 'None' : `${runtime.llmProvider} / ${runtime.llmModel}`}</span>
      </p>

      <div className="mt-2 space-y-3">
        <div className="flex flex-col gap-1">
          <span>Порт подключения</span>
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded border border-slate-300 p-2"
              value={draft.llmBase}
              onChange={(event) => setDraft((current) => ({ ...current, llmBase: event.target.value }))}
              placeholder={getDefaultOllamaBase()}
            />
            <button type="button" className="rounded border px-2 py-1 text-slate-900" onClick={acceptPort}>
              Принять
            </button>
          </div>
        </div>

        <label className="flex flex-col gap-1">
          <span>Поставщик</span>
          <select
            className="rounded border border-slate-300 p-2"
            value={draft.provider}
            onChange={(event) => setDraft((current) => ({ ...current, provider: event.target.value as LlmProvider }))}
          >
            <option value="none">None</option>
            <option value="ollama">Ollama</option>
            <option value="openai">OpenAI-compatible</option>
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span>Модель</span>
          <select
            className="rounded border border-slate-300 p-2"
            value={draft.model}
            onChange={(event) => setDraft((current) => ({ ...current, model: event.target.value }))}
            disabled={(draft.provider !== 'ollama' && draft.provider !== 'openai') || (draft.provider === 'ollama' && loadingModels) || (draft.provider === 'ollama' && models.length === 0)}
          >
            {draft.provider === 'none' ? <option value="">None</option> : null}
            {draft.provider === 'openai' ? <option value={draft.model || 'gpt-4o-mini'}>{draft.model || 'gpt-4o-mini'}</option> : null}
            {draft.provider === 'ollama' && models.length === 0 ? <option value="">{loadingModels ? 'Загрузка моделей...' : 'Нет моделей'}</option> : null}
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span>Лимит истории чата (1..50)</span>
          <input
            type="number"
            min={1}
            max={50}
            className="rounded border border-slate-300 p-2"
            value={draft.maxHistory}
            onChange={(event) => setDraft((current) => ({ ...current, maxHistory: Math.min(50, Math.max(1, Number(event.target.value) || 5)) }))}
          />
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={draft.debugModelMode}
            onChange={(event) => setDraft((current) => ({ ...current, debugModelMode: event.target.checked }))}
          />
          <span>debug_model_mode (включает детальные логи отправки)</span>
        </label>
      </div>

      {modelsError ? <p className="mt-2 text-[11px] text-red-600">{modelsError}</p> : null}
      {info ? <p className="mt-2 text-[11px] text-slate-500">{info}</p> : null}

      <div className="mt-3 grid grid-cols-3 gap-2">
        <button type="button" className="rounded border px-2 py-1 text-slate-900" onClick={connect}>
          Подключить
        </button>
        <button type="button" className="rounded border px-2 py-1 text-slate-900" onClick={saveDraft}>
          Сохранить
        </button>
        <button type="button" className="rounded border border-red-200 px-2 py-1 text-red-600" onClick={disconnect}>
          Отключить
        </button>
      </div>
    </div>
  );
}
