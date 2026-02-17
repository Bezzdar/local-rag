export type RuntimeConfig = {
  apiBase: string;
  llmProvider: string;
  llmModel: string;
};

const CONFIG_STORAGE_KEY = 'rag.runtime-config';

const DEFAULT_CONFIG: RuntimeConfig = {
  apiBase: process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000',
  llmProvider: 'ollama',
  llmModel: 'llama3.1:8b',
};

function sanitizeApiBase(value: string): string {
  const trimmed = value.trim();
  return trimmed ? trimmed.replace(/\/+$/, '') : DEFAULT_CONFIG.apiBase;
}

export function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === 'undefined') {
    return DEFAULT_CONFIG;
  }

  const raw = window.localStorage.getItem(CONFIG_STORAGE_KEY);
  if (!raw) {
    return DEFAULT_CONFIG;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<RuntimeConfig>;
    return {
      apiBase: sanitizeApiBase(parsed.apiBase ?? DEFAULT_CONFIG.apiBase),
      llmProvider: (parsed.llmProvider ?? DEFAULT_CONFIG.llmProvider).trim() || DEFAULT_CONFIG.llmProvider,
      llmModel: (parsed.llmModel ?? DEFAULT_CONFIG.llmModel).trim() || DEFAULT_CONFIG.llmModel,
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function setRuntimeConfig(next: RuntimeConfig): RuntimeConfig {
  const normalized: RuntimeConfig = {
    apiBase: sanitizeApiBase(next.apiBase),
    llmProvider: next.llmProvider.trim() || DEFAULT_CONFIG.llmProvider,
    llmModel: next.llmModel.trim() || DEFAULT_CONFIG.llmModel,
  };

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(normalized));
    window.dispatchEvent(new CustomEvent('rag-runtime-config-changed', { detail: normalized }));
  }

  return normalized;
}
