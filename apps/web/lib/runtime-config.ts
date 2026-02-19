export type LlmProvider = 'none' | 'ollama';

export type RuntimeConfig = {
  llmBase: string;
  llmProvider: LlmProvider;
  llmModel: string;
};

const CONFIG_STORAGE_KEY = 'rag.runtime-config';
const DEFAULT_OLLAMA_BASE = 'http://10.0.10.153:11434';

const DEFAULT_CONFIG: RuntimeConfig = {
  llmBase: DEFAULT_OLLAMA_BASE,
  llmProvider: 'none',
  llmModel: '',
};

function sanitizeUrl(value: string): string {
  return value.trim().replace(/\/+$/, '');
}

function normalizeProvider(value: string | undefined): LlmProvider {
  return value === 'ollama' ? 'ollama' : 'none';
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
      llmBase: sanitizeUrl(parsed.llmBase ?? DEFAULT_CONFIG.llmBase),
      llmProvider: normalizeProvider(parsed.llmProvider),
      llmModel: (parsed.llmModel ?? DEFAULT_CONFIG.llmModel).trim(),
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function setRuntimeConfig(next: RuntimeConfig): RuntimeConfig {
  const normalized: RuntimeConfig = {
    llmBase: sanitizeUrl(next.llmBase || DEFAULT_CONFIG.llmBase),
    llmProvider: normalizeProvider(next.llmProvider),
    llmModel: next.llmModel.trim(),
  };

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(normalized));
    window.dispatchEvent(new CustomEvent('rag-runtime-config-changed', { detail: normalized }));
  }

  return normalized;
}

export function getDefaultOllamaBase(): string {
  return DEFAULT_OLLAMA_BASE;
}
