import { useSyncExternalStore } from 'react';

type ChatState = {
  isClearing: boolean;
  pendingClearId: number | null;
  lastClearId: number;
};

let state: ChatState = {
  isClearing: false,
  pendingClearId: null,
  lastClearId: 0,
};

const listeners = new Set<() => void>();
const activeStreamClosers = new Map<string, () => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function beginClear(): number {
  const clearId = Date.now();
  state = { ...state, isClearing: true, pendingClearId: clearId };
  activeStreamClosers.forEach((close) => close());
  activeStreamClosers.clear();
  emit();
  return clearId;
}

export function finishClear(clearId: number) {
  if (state.pendingClearId !== clearId) {
    return;
  }
  state = { isClearing: false, pendingClearId: null, lastClearId: clearId };
  emit();
}

export function failClear(clearId: number) {
  if (state.pendingClearId !== clearId) {
    return;
  }
  state = { ...state, isClearing: false, pendingClearId: null };
  emit();
}

export function registerStreamCloser(streamId: string, closer: () => void) {
  activeStreamClosers.set(streamId, closer);
}

export function unregisterStreamCloser(streamId: string) {
  activeStreamClosers.delete(streamId);
}

export function shouldIgnoreStream(streamStartedAt: number): boolean {
  const pending = state.pendingClearId ?? 0;
  return streamStartedAt <= Math.max(state.lastClearId, pending);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

export function useChatStore() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
