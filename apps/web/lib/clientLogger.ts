const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '');

type ClientEventPayload = {
  event: string;
  notebookId?: string;
  metadata?: Record<string, unknown>;
};

export function logClientEvent(payload: ClientEventPayload) {
  const body = JSON.stringify({
    event: payload.event,
    source: 'web',
    notebook_id: payload.notebookId,
    metadata: payload.metadata ?? {},
  });

  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    const blob = new Blob([body], { type: 'application/json' });
    navigator.sendBeacon(`${apiBase}/api/client-events`, blob);
    return;
  }

  void fetch(`${apiBase}/api/client-events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => undefined);
}
