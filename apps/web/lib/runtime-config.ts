export type LlmProvider = 'none' | 'ollama' | 'openai';

export type RuntimeConfig = {
  llmBase: string;
  llmProvider: LlmProvider;
  llmModel: string;
  maxHistory: number;
  debugModelMode: boolean;
};

const CONFIG_STORAGE_KEY = 'rag.runtime-config';
const DEFAULT_OLLAMA_BASE = 'http://10.0.10.153:11434';

const DEFAULT_CONFIG: RuntimeConfig = {
  llmBase: DEFAULT_OLLAMA_BASE,
  llmProvider: 'none',
  llmModel: '',
  maxHistory: 5,
  debugModelMode: false,
};

function sanitizeUrl(value: string): string {
  return value.trim().replace(/\/+$/, '');
}

function normalizeProvider(value: string | undefined): LlmProvider {
  if (value === 'ollama' || value === 'openai') {
    return value;
  }
  return 'none';
}

function normalizeMaxHistory(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return DEFAULT_CONFIG.maxHistory;
  }
  return Math.min(50, Math.max(1, Math.trunc(parsed)));
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
      maxHistory: normalizeMaxHistory(parsed.maxHistory),
      debugModelMode: Boolean(parsed.debugModelMode),
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
    maxHistory: normalizeMaxHistory(next.maxHistory),
    debugModelMode: Boolean(next.debugModelMode),
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
