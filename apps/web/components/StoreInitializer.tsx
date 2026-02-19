'use client';

import { useEffect } from 'react';
import { initializeConnectionStore, setKeepAlive } from '@/src/stores/connectionStore';
import { initializeModeStore } from '@/src/stores/modeStore';

export default function StoreInitializer() {
  useEffect(() => {
    initializeConnectionStore();
    initializeModeStore();
    setKeepAlive(true);
  }, []);

  return null;
}
