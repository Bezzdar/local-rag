'use client';

import { getRuntimeConfig, RuntimeConfig, setRuntimeConfig } from '@/lib/runtime-config';
import { useEffect, useState } from 'react';

export default function RuntimeSettings() {
  const [config, setConfig] = useState<RuntimeConfig>(() => getRuntimeConfig());

  useEffect(() => {
    const listener = (event: Event) => {
      const customEvent = event as CustomEvent<RuntimeConfig>;
      if (customEvent.detail) {
        setConfig(customEvent.detail);
      }
    };

    window.addEventListener('rag-runtime-config-changed', listener);
    return () => window.removeEventListener('rag-runtime-config-changed', listener);
  }, []);

  const persist = () => {
    setConfig(setRuntimeConfig(config));
  };

  return (
    <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
      <p className="font-medium text-slate-900">Настройки подключения</p>
      <div className="mt-2 grid gap-2 md:grid-cols-3">
        <label className="flex flex-col gap-1">
          <span>API URL (порт)</span>
          <input
            className="rounded border border-slate-300 p-2"
            value={config.apiBase}
            onChange={(event) => setConfig((current) => ({ ...current, apiBase: event.target.value }))}
            placeholder="http://localhost:8000"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span>Провайдер</span>
          <input
            className="rounded border border-slate-300 p-2"
            value={config.llmProvider}
            onChange={(event) => setConfig((current) => ({ ...current, llmProvider: event.target.value }))}
            placeholder="ollama"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span>Модель</span>
          <input
            className="rounded border border-slate-300 p-2"
            value={config.llmModel}
            onChange={(event) => setConfig((current) => ({ ...current, llmModel: event.target.value }))}
            placeholder="llama3.1:8b"
          />
        </label>
      </div>
      <button className="mt-2 rounded border px-2 py-1 text-slate-900" onClick={persist}>
        Сохранить настройки
      </button>
    </div>
  );
}
