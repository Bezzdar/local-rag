import { AgentManifest } from '@/types/dto';
import { useSyncExternalStore } from 'react';

const AGENT_STORAGE_KEY = 'selected-agent-id';

type AgentState = { selectedAgentId: string };

let state: AgentState = { selectedAgentId: '' };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function readStoredAgentId(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.localStorage.getItem(AGENT_STORAGE_KEY) ?? '';
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

export function syncSelectedAgentWithManifest(agents: AgentManifest[]) {
  const validIds = new Set(agents.map((agent) => agent.id));
  const preferred = state.selectedAgentId;
  if (preferred && validIds.has(preferred)) {
    return;
  }

  const fallback = agents[0]?.id ?? '';
  if (fallback !== preferred) {
    setSelectedAgent(fallback);
  }
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
