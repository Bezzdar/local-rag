export type SseEvents = {
  onToken: (token: string) => void;
  onCitations: (citations: unknown) => void;
  onDone: (messageId: string) => void;
  onError: (err: Error) => void;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

export function streamChat(params: {
  notebookId: string;
  message: string;
  mode: 'qa' | 'draft' | 'table' | 'summarize';
  selectedSourceIds: string[];
  events: SseEvents;
}): () => void {
  const search = new URLSearchParams({
    notebook_id: params.notebookId,
    message: params.message,
    mode: params.mode,
    selected_source_ids: params.selectedSourceIds.join(','),
  });
  const es = new EventSource(`${API_BASE}/api/chat/stream?${search.toString()}`);
  es.addEventListener('token', (e) => params.events.onToken(JSON.parse((e as MessageEvent).data).text));
  es.addEventListener('citations', (e) => params.events.onCitations(JSON.parse((e as MessageEvent).data)));
  es.addEventListener('done', (e) => {
    params.events.onDone(JSON.parse((e as MessageEvent).data).message_id);
    es.close();
  });
  es.onerror = () => {
    params.events.onError(new Error('SSE connection failed'));
    es.close();
  };
  return () => es.close();
}
