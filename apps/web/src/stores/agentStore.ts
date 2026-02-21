import { useSyncExternalStore } from 'react';

const AGENT_STORAGE_KEY = 'selected-agent-id';

type AgentState = { selectedAgentId: string };

let state: AgentState = { selectedAgentId: 'agent_001' };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function readStoredAgentId(): string {
  if (typeof window === 'undefined') {
    return 'agent_001';
  }
  return window.localStorage.getItem(AGENT_STORAGE_KEY) ?? 'agent_001';
}

export function initializeAgentStore() {
  state = { selectedAgentId: readStoredAgentId() };
}

export function setSelectedAgent(agentId: string) {
  state = { selectedAgentId: agentId };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(AGENT_STORAGE_KEY, agentId);
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

export function useAgentStore() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
