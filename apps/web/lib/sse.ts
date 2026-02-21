import { logClientEvent } from '@/lib/clientLogger';
import { getRuntimeConfig } from '@/lib/runtime-config';

export type ChatMode = 'model' | 'agent' | 'rag';

export const CHAT_MODE_OPTIONS: Array<{ value: ChatMode; label: string }> = [
  { value: 'model', label: 'Модель' },
  { value: 'agent', label: 'Агент' },
  { value: 'rag', label: 'RAG' },
];

const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '');

export type StreamHandlers = {
  onToken: (text: string) => void;
  onCitations: (payload: unknown) => void;
  onDone: (messageId: string) => void;
  onError: (error: Error) => void;
};

export function openChatStream(params: {
  notebookId: string;
  message: string;
  mode: ChatMode;
  agentId?: string;
  selectedSourceIds: string[];
  handlers: StreamHandlers;
}): () => void {
  const runtimeConfig = getRuntimeConfig();
  const search = new URLSearchParams({
    notebook_id: params.notebookId,
    message: params.message,
    mode: params.mode,
    selected_source_ids: params.selectedSourceIds.join(','),
    provider: runtimeConfig.llmProvider,
    model: runtimeConfig.llmModel,
    base_url: runtimeConfig.llmBase,
    max_history: String(runtimeConfig.maxHistory),
    ...(params.agentId ? { agent_id: params.agentId } : {}),
  });

  if (runtimeConfig.debugModelMode) {
    console.log('[model-mode] openChatStream params', Object.fromEntries(search.entries()));
  }

  const streamUrl = `${apiBase}/api/chat/stream?${search.toString()}`;
  let packets = 0;
  let doneReceived = false;
  const streamStartedAt = Date.now();
  const eventSource = new EventSource(streamUrl);
  logClientEvent({
    event: 'stream.open',
    notebookId: params.notebookId,
    metadata: { mode: params.mode, selectedSourceCount: params.selectedSourceIds.length },
  });
  eventSource.addEventListener('token', (event) => {
    const text = JSON.parse((event as MessageEvent).data).text as string;
    packets += 1;
    params.handlers.onToken(text);
  });
  eventSource.addEventListener('citations', (event) => {
    params.handlers.onCitations(JSON.parse((event as MessageEvent).data));
  });
  eventSource.addEventListener('done', (event) => {
    const messageId = JSON.parse((event as MessageEvent).data).message_id as string;
    doneReceived = true;
    logClientEvent({
      event: 'stream.done',
      notebookId: params.notebookId,
      metadata: { packets, durationMs: Date.now() - streamStartedAt, messageId },
    });
    params.handlers.onDone(messageId);
    eventSource.close();
  });
  eventSource.addEventListener('error', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as { detail?: string };
    logClientEvent({
      event: 'stream.error',
      notebookId: params.notebookId,
      metadata: { packets, durationMs: Date.now() - streamStartedAt, detail: payload.detail ?? 'SSE model error' },
    });
    params.handlers.onError(new Error(payload.detail ?? 'SSE model error'));
    eventSource.close();
  });

  eventSource.onerror = () => {
    logClientEvent({
      event: doneReceived ? 'stream.closed' : 'stream.disconnected',
      notebookId: params.notebookId,
      metadata: { packets, durationMs: Date.now() - streamStartedAt, doneReceived },
    });
    params.handlers.onError(new Error('SSE disconnected'));
    eventSource.close();
  };

  return () => {
    logClientEvent({
      event: 'stream.closed_by_client',
      notebookId: params.notebookId,
      metadata: { packets, durationMs: Date.now() - streamStartedAt, doneReceived },
    });
    eventSource.close();
  };
}
