'use client';

import { useConnectionStore } from '@/src/stores/connectionStore';

export default function ConnectionIndicator() {
  const connection = useConnectionStore();

  const providerLabel = connection.provider === 'openai' ? 'OpenAI-compatible' : 'Ollama';

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600" title={connection.isConnected ? `Подключено к ${providerLabel} / ${connection.currentModel}` : 'LLM не подключен'}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${connection.isConnected ? 'bg-emerald-500' : 'bg-slate-400'}`} />
      <span>{connection.isConnected ? `Connected: ${providerLabel} / ${connection.currentModel}` : 'Disconnected'}</span>
    </div>
  );
}
