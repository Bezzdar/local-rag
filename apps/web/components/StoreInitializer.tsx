'use client';

import { useEffect } from 'react';
import { initializeConnectionStore, setKeepAlive } from '@/src/stores/connectionStore';
import { initializeModeStore } from '@/src/stores/modeStore';
import { initializeAgentStore } from '@/src/stores/agentStore';
import { getRuntimeConfig, setRuntimeConfig } from '@/lib/runtime-config';

export default function StoreInitializer() {
  useEffect(() => {
    const runtime = getRuntimeConfig();
    setRuntimeConfig({
      ...runtime,
      llmProvider: 'none',
      llmModel: '',
    });
    initializeConnectionStore();
    initializeModeStore();
    initializeAgentStore();
    setKeepAlive(true);
  }, []);

  return null;
}
