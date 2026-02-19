import { ChatMode } from '@/lib/sse';
import { useSyncExternalStore } from 'react';

const MODE_STORAGE_KEY = 'chat-mode';

type ModeState = { currentMode: ChatMode };

let state: ModeState = { currentMode: 'rag' };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function readStoredMode(): ChatMode {
  if (typeof window === 'undefined') {
    return 'rag';
  }
  const savedMode = window.localStorage.getItem(MODE_STORAGE_KEY);
  return savedMode === 'model' || savedMode === 'agent' || savedMode === 'rag' ? savedMode : 'rag';
}

export function initializeModeStore() {
  state = { currentMode: readStoredMode() };
}

export function setCurrentMode(mode: ChatMode) {
  state = { currentMode: mode };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode);
  }
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

export function useModeStore() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
