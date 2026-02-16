export type ChatMode = 'qa' | 'draft' | 'table' | 'summarize';

export type StreamHandlers = {
  onToken: (text: string) => void;
  onCitations: (payload: unknown) => void;
  onDone: (messageId: string) => void;
  onError: (error: Error) => void;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

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
  });

  const eventSource = new EventSource(`${API_BASE}/api/chat/stream?${search.toString()}`);
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
