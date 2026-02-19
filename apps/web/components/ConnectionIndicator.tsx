'use client';

import { useConnectionStore } from '@/src/stores/connectionStore';

export default function ConnectionIndicator() {
  const connection = useConnectionStore();

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600" title={connection.isConnected ? `Подключено к ${connection.currentModel}` : 'LLM не подключен'}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${connection.isConnected ? 'bg-emerald-500' : 'bg-slate-400'}`} />
      <span>{connection.isConnected ? `Connected: ${connection.currentModel}` : 'Disconnected'}</span>
    </div>
  );
}
