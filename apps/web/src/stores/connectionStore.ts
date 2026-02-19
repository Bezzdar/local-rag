import { getRuntimeConfig, RuntimeConfig } from '@/lib/runtime-config';
import { useSyncExternalStore } from 'react';

type ConnectionState = {
  isConnected: boolean;
  currentModel: string;
  provider: RuntimeConfig['llmProvider'];
  keepAlive: boolean;
};

let state: ConnectionState = {
  isConnected: false,
  currentModel: '',
  provider: 'none',
  keepAlive: true,
};

const listeners = new Set<() => void>();
let initialized = false;

function emit() {
  listeners.forEach((listener) => listener());
}

function deriveFromRuntime(runtime: RuntimeConfig): ConnectionState {
  const connected = runtime.llmProvider !== 'none' && runtime.llmModel.trim().length > 0;
  return {
    ...state,
    isConnected: connected,
    currentModel: connected ? runtime.llmModel : '',
    provider: runtime.llmProvider,
  };
}

export function initializeConnectionStore() {
  state = deriveFromRuntime(getRuntimeConfig());
  if (initialized || typeof window === 'undefined') {
    return;
  }
  initialized = true;
  window.addEventListener('rag-runtime-config-changed', (event: Event) => {
    const detail = (event as CustomEvent<RuntimeConfig>).detail;
    state = deriveFromRuntime(detail ?? getRuntimeConfig());
    emit();
  });
}

export function setKeepAlive(keepAlive: boolean) {
  state = { ...state, keepAlive };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

export function useConnectionStore() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
