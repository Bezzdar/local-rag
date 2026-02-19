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

let runtimeConfigState: RuntimeConfig = DEFAULT_CONFIG;
let runtimeHydrated = false;

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

  if (!runtimeHydrated) {
    runtimeHydrated = true;
    window.localStorage.removeItem(CONFIG_STORAGE_KEY);
  }

  return runtimeConfigState;
}

export function setRuntimeConfig(next: RuntimeConfig): RuntimeConfig {
  const normalized: RuntimeConfig = {
    llmBase: sanitizeUrl(next.llmBase || DEFAULT_CONFIG.llmBase),
    llmProvider: normalizeProvider(next.llmProvider),
    llmModel: next.llmModel.trim(),
    maxHistory: normalizeMaxHistory(next.maxHistory),
    debugModelMode: Boolean(next.debugModelMode),
  };

  runtimeConfigState = normalized;

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('rag-runtime-config-changed', { detail: normalized }));
  }

  return normalized;
}

export function getDefaultOllamaBase(): string {
  return DEFAULT_OLLAMA_BASE;
}
