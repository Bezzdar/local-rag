import { getRuntimeConfig } from '@/lib/runtime-config';

export type ChatMode = 'qa' | 'draft' | 'table' | 'summarize';

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
  selectedSourceIds: string[];
  handlers: StreamHandlers;
}): () => void {
  const search = new URLSearchParams({
    notebook_id: params.notebookId,
    message: params.message,
    mode: params.mode,
    selected_source_ids: params.selectedSourceIds.join(','),
    provider: getRuntimeConfig().llmProvider,
    model: getRuntimeConfig().llmModel,
  });

  const { apiBase } = getRuntimeConfig();
  const eventSource = new EventSource(`${apiBase}/api/chat/stream?${search.toString()}`);
  eventSource.addEventListener('token', (event) => {
    const text = JSON.parse((event as MessageEvent).data).text as string;
    params.handlers.onToken(text);
  });
  eventSource.addEventListener('citations', (event) => {
    params.handlers.onCitations(JSON.parse((event as MessageEvent).data));
  });
  eventSource.addEventListener('done', (event) => {
    const messageId = JSON.parse((event as MessageEvent).data).message_id as string;
    params.handlers.onDone(messageId);
    eventSource.close();
  });

  eventSource.onerror = () => {
    params.handlers.onError(new Error('SSE disconnected'));
    eventSource.close();
  };

  return () => eventSource.close();
}
