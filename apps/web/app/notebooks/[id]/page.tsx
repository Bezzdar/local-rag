'use client';

import ChatPanel from '@/components/ChatPanel';
import ConnectionIndicator from '@/components/ConnectionIndicator';
import EvidencePanel from '@/components/EvidencePanel';
import SourcesPanel from '@/components/SourcesPanel';
import { api, CitationsSchema } from '@/lib/api';
import { logClientEvent } from '@/lib/clientLogger';
import { ChatMode, openChatStream } from '@/lib/sse';
import { getRuntimeConfig } from '@/lib/runtime-config';
import { Citation, Source } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { beginClear, failClear, finishClear, registerStreamCloser, shouldIgnoreStream, unregisterStreamCloser, useChatStore } from '@/src/stores/chatStore';
import { setKeepAlive } from '@/src/stores/connectionStore';
import { setCurrentMode, useModeStore } from '@/src/stores/modeStore';
import { setSelectedAgent, useAgentStore } from '@/src/stores/agentStore';

const LEFT_MIN = 240;
const LEFT_MAX = 520;
const RIGHT_MIN = 280;
const RIGHT_MAX = 640;

type SourceConfigModalState = {
  source: Source;
  useGlobalChunkSize: boolean;
  useGlobalOverlap: boolean;
  useGlobalOcrEnabled: boolean;
  useGlobalOcrLanguage: boolean;
  chunkSize: string;
  chunkOverlap: string;
  ocrEnabled: boolean;
  ocrLanguage: string;
};

export default function NotebookWorkspacePage() {
  const params = useParams<{ id: string }>();
  const notebookId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const { currentMode } = useModeStore();
  const { selectedAgentId } = useAgentStore();
  const { isClearing } = useChatStore();
  const [streaming, setStreaming] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [explicitSelection, setExplicitSelection] = useState<string[] | null>(null);
  const closeStreamRef = useRef<(() => void) | null>(null);

  const [leftWidth, setLeftWidth] = useState(320);
  const [rightWidth, setRightWidth] = useState(360);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [sourceConfigModal, setSourceConfigModal] = useState<SourceConfigModalState | null>(null);

  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const notebookExists = notebooks.data?.some((notebook) => notebook.id === notebookId) ?? false;
  const hasAnyNotebook = (notebooks.data?.length ?? 0) > 0;
  const fallbackNotebookId = notebooks.data?.[0]?.id;
  const allowNotebookQueries = notebooks.isSuccess && notebookExists;

  const agents = useQuery({ queryKey: ['agents'], queryFn: api.listAgents });

  const sources = useQuery({ queryKey: ['sources', notebookId], queryFn: () => api.listSources(notebookId), enabled: allowNotebookQueries });
  const messages = useQuery({ queryKey: ['messages', notebookId], queryFn: () => api.listMessages(notebookId), enabled: allowNotebookQueries });
  const notes = useQuery({ queryKey: ['notes', notebookId], queryFn: () => api.listNotes(notebookId), enabled: allowNotebookQueries });
  const parsingSettings = useQuery({ queryKey: ['parsing-settings', notebookId], queryFn: () => api.getParsingSettings(notebookId), enabled: allowNotebookQueries });


  const uploadSource = useMutation({
    mutationFn: (file: File) => api.uploadSource(notebookId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const deleteSources = useMutation({
    mutationFn: (sourceIds: string[]) => Promise.all(sourceIds.map((sourceId) => api.deleteSource(sourceId))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const eraseSource = useMutation({
    mutationFn: (sourceId: string) => api.eraseSource(sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const reparseSource = useMutation({
    mutationFn: (sourceId: string) => api.reparseSource(sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const updateSource = useMutation({
    mutationFn: ({ sourceId, payload }: { sourceId: string; payload: { is_enabled?: boolean; individual_config?: { chunk_size: number | null; chunk_overlap: number | null; ocr_enabled: boolean | null; ocr_language: string | null } } }) => api.updateSource(sourceId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const createNote = useMutation({
    mutationFn: ({ title, content }: { title: string; content: string }) => api.createNote(notebookId, title, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes', notebookId] }),
  });

  const clearChat = useMutation({
    mutationFn: () => api.clearMessages(notebookId),
    onMutate: async () => {
      const clearId = beginClear();
      await queryClient.cancelQueries({ queryKey: ['messages', notebookId] });
      queryClient.setQueryData(['messages', notebookId], []);
      setStreaming('');
      setCitations([]);
      return { clearId };
    },
    onSuccess: (_data, _vars, context) => {
      if (context) {
        finishClear(context.clearId);
      }
      queryClient.invalidateQueries({ queryKey: ['messages', notebookId] });
    },
    onError: (_error, _vars, context) => {
      if (context) {
        failClear(context.clearId);
      }
    },
  });

  const allSourceIds = useMemo(() => sources.data?.filter((source) => source.is_enabled ?? true).map((source) => source.id) ?? [], [sources.data]);

  const selectedSourceIds = useMemo(() => {
    if (!sources.data) {
      return [];
    }
    return explicitSelection ?? allSourceIds;
  }, [allSourceIds, explicitSelection, sources.data]);

  useEffect(() => {
    setExplicitSelection((current) => {
      if (current === null) {
        return null;
      }
      return current.filter((sourceId) => allSourceIds.includes(sourceId));
    });
  }, [allSourceIds]);

  useEffect(() => {
    setKeepAlive(true);
    return () => {
      setKeepAlive(true);
    };
  }, []);

  useEffect(
    () => () => {
      closeStreamRef.current?.();
      closeStreamRef.current = null;
    },
    [],
  );

  useEffect(() => {
    if (!notebooks.isSuccess) {
      return;
    }

    if (!hasAnyNotebook) {
      router.replace('/notebooks');
      return;
    }

    if (!notebookExists && fallbackNotebookId) {
      router.replace(`/notebooks/${fallbackNotebookId}`);
    }
  }, [fallbackNotebookId, hasAnyNotebook, notebookExists, notebooks.isSuccess, router]);

  const sendMessage = (text: string) => {
    logClientEvent({ event: 'ui.message.send_attempt', notebookId, metadata: { length: text.length, mode: currentMode } });
    if (isClearing || clearChat.isPending) {
      return;
    }

    closeStreamRef.current?.();
    setStreaming('');
    setCitations([]);
    const streamStartedAt = Date.now();
    const streamId = `${notebookId}-${streamStartedAt}`;

    const streamMode: ChatMode = currentMode === 'model' ? 'model' : currentMode;
    const runtimeConfig = getRuntimeConfig();
    if (runtimeConfig.debugModelMode) {
      console.log('[model-mode] sendMessage', {
        mode: streamMode,
        provider: runtimeConfig.llmProvider,
        model: runtimeConfig.llmModel,
        baseUrl: runtimeConfig.llmBase,
        maxHistory: runtimeConfig.maxHistory,
      });
    }

    const close = openChatStream({
      notebookId,
      message: text,
      mode: streamMode,
      agentId: currentMode === 'agent' ? selectedAgentId : undefined,
      selectedSourceIds,
      handlers: {
        onToken: (token) => {
          if (shouldIgnoreStream(streamStartedAt)) {
            return;
          }
          setStreaming((value) => value + token);
        },
        onCitations: (payload) => {
          if (shouldIgnoreStream(streamStartedAt)) {
            return;
          }
          setCitations(CitationsSchema.parse(payload));
        },
        onDone: () => {
          unregisterStreamCloser(streamId);
          if (!shouldIgnoreStream(streamStartedAt)) {
            queryClient.invalidateQueries({ queryKey: ['messages', notebookId] });
            setStreaming('');
          }
          closeStreamRef.current = null;
          close();
        },
        onError: () => {
          closeStreamRef.current = null;
          unregisterStreamCloser(streamId);
          close();
        },
      },
    });
    closeStreamRef.current = close;
    registerStreamCloser(streamId, close);
  };

  const handleToggleSource = (sourceId: string) => {
    logClientEvent({ event: 'ui.source.toggle', notebookId, metadata: { sourceId } });
    setExplicitSelection((current) => {
      const baseSelection = current ?? allSourceIds;
      return baseSelection.includes(sourceId)
        ? baseSelection.filter((id) => id !== sourceId)
        : [...baseSelection, sourceId];
    });
  };

  const handleDeleteSources = (sourceIds: string[], confirmText: string) => {
    logClientEvent({ event: 'ui.sources.delete_requested', notebookId, metadata: { count: sourceIds.length } });
    if (sourceIds.length === 0 || deleteSources.isPending) {
      return;
    }
    if (!window.confirm(confirmText)) {
      return;
    }
    deleteSources.mutate(sourceIds, {
      onSuccess: () => {
        setExplicitSelection((current) => {
          if (current === null) {
            return null;
          }
          return current.filter((sourceId) => !sourceIds.includes(sourceId));
        });
      },
    });
  };

  const startResize = (side: 'left' | 'right') => {
    const handleMove = (event: MouseEvent) => {
      if (side === 'left') {
        setLeftCollapsed(false);
        setLeftWidth(Math.min(LEFT_MAX, Math.max(LEFT_MIN, event.clientX)));
        return;
      }
      const widthFromRight = window.innerWidth - event.clientX;
      setRightCollapsed(false);
      setRightWidth(Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, widthFromRight)));
    };

    const stop = () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', stop);
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', stop);
  };

  if (notebooks.isLoading || (allowNotebookQueries && (sources.isLoading || messages.isLoading || notes.isLoading || parsingSettings.isLoading))) {
    return <div className="p-6">Loading workspace...</div>;
  }
  if (notebooks.isError || (allowNotebookQueries && (sources.isError || messages.isError || notes.isError || parsingSettings.isError))) {
    return <div className="p-6">Failed to load notebook workspace.</div>;
  }
  if (!allowNotebookQueries) {
    return <div className="p-6">Notebook not found. Redirecting…</div>;
  }
  if (!notebooks.data || !sources.data || !messages.data || !notes.data || !parsingSettings.data) {
    return <div className="p-6">Failed to load notebook workspace.</div>;
  }

  return (
    <div className="min-h-screen p-3 lg:h-screen">
      <div className="mb-2">
        <ConnectionIndicator />
      </div>
      <div className="mt-3 flex h-[calc(100%-84px)]">
        <div style={{ width: leftCollapsed ? 44 : leftWidth }} className="h-full shrink-0 bg-white border-r border-slate-200">
          <div className="flex items-center justify-end p-2 border-b border-slate-200">
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs"
              onClick={() => {
                logClientEvent({ event: 'ui.left_panel.toggle', notebookId, metadata: { collapsed: !leftCollapsed } });
                setLeftCollapsed((value) => !value);
              }}
              aria-label={leftCollapsed ? 'Развернуть левую панель' : 'Свернуть левую панель'}
            >
              {leftCollapsed ? '⟩' : '⟨'}
            </button>
          </div>
          {!leftCollapsed ? (
            <SourcesPanel
              notebooks={notebooks.data}
              activeNotebookId={notebookId}
              sources={sources.data}
              selectedSourceIds={selectedSourceIds}
              onNotebookChange={(id) => router.push(`/notebooks/${id}`)}
              onToggleSource={handleToggleSource}
              onSelectAllSources={() => { logClientEvent({ event: 'ui.sources.select_all', notebookId }); setExplicitSelection(allSourceIds); }}
              onClearSourceSelection={() => { logClientEvent({ event: 'ui.sources.deselect_all', notebookId }); setExplicitSelection([]); }}
              onDeleteSelectedSources={() => {
                handleDeleteSources(selectedSourceIds, `Удалить ${selectedSourceIds.length} выбранных документов?`);
              }}
              onDeleteUnselectedSources={() => {
                const unselected = sources.data
                  .filter((source) => !selectedSourceIds.includes(source.id))
                  .map((source) => source.id);
                handleDeleteSources(unselected, `Удалить ${unselected.length} невыбранных документов?`);
              }}
              onParseAllSources={() => {
                const ids = sources.data.map((s) => s.id);
                if (ids.length === 0) return;
                logClientEvent({ event: 'ui.sources.reparse_all', notebookId, metadata: { count: ids.length } });
                ids.forEach((id) => reparseSource.mutate(id));
              }}
              onParseSelectedSources={() => {
                if (selectedSourceIds.length === 0) return;
                logClientEvent({ event: 'ui.sources.reparse_selected', notebookId, metadata: { count: selectedSourceIds.length } });
                selectedSourceIds.forEach((id) => reparseSource.mutate(id));
              }}
              onUpload={(file) => { logClientEvent({ event: 'ui.source.upload', notebookId, metadata: { filename: file.name, size: file.size } }); uploadSource.mutate(file); }}
              onDeleteSource={(source) => handleDeleteSources([source.id], `Удалить документ ${source.filename} и все связанные данные?`)}
              onEraseSource={(source) => {
                if (window.confirm(`Стереть parsing/base данные для ${source.filename}?`)) {
                  logClientEvent({ event: 'ui.source.erase', notebookId, metadata: { sourceId: source.id, filename: source.filename } });
                  eraseSource.mutate(source.id);
                }
              }}
              onParseSource={(source) => { logClientEvent({ event: 'ui.source.reparse', notebookId, metadata: { sourceId: source.id, filename: source.filename } }); reparseSource.mutate(source.id); }}
              onOpenConfig={(source) => {
                logClientEvent({ event: 'ui.source.config_open', notebookId, metadata: { sourceId: source.id, filename: source.filename } });
                setSourceConfigModal({
                  source,
                  useGlobalChunkSize: source.individual_config?.chunk_size === null || source.individual_config?.chunk_size === undefined,
                  useGlobalOverlap: source.individual_config?.chunk_overlap === null || source.individual_config?.chunk_overlap === undefined,
                  useGlobalOcrEnabled: source.individual_config?.ocr_enabled === null || source.individual_config?.ocr_enabled === undefined,
                  useGlobalOcrLanguage: source.individual_config?.ocr_language === null || source.individual_config?.ocr_language === undefined,
                  chunkSize: String(source.individual_config?.chunk_size ?? parsingSettings.data.chunk_size),
                  chunkOverlap: String(source.individual_config?.chunk_overlap ?? parsingSettings.data.chunk_overlap),
                  ocrEnabled: source.individual_config?.ocr_enabled ?? parsingSettings.data.ocr_enabled,
                  ocrLanguage: source.individual_config?.ocr_language ?? parsingSettings.data.ocr_language,
                });
              }}
            />
          ) : null}
        </div>

        <div
          className="hidden lg:block w-2 cursor-col-resize bg-slate-100 hover:bg-slate-300"
          onMouseDown={() => startResize('left')}
          title="Изменить ширину левой панели"
        />

        <ChatPanel
          notebookId={notebookId}
          mode={currentMode}
          agentId={selectedAgentId}
          agents={agents.data ?? []}
          messages={messages.data}
          streaming={streaming}
          citations={citations}
          onModeChange={(nextMode) => { logClientEvent({ event: 'ui.chat.mode_change', notebookId, metadata: { from: currentMode, to: nextMode } }); setCurrentMode(nextMode as ChatMode); }}
          onAgentChange={(agentId) => { logClientEvent({ event: 'ui.chat.agent_change', notebookId, metadata: { agentId } }); setSelectedAgent(agentId); }}
          onSend={sendMessage}
          disableSend={isClearing || clearChat.isPending}
          sendDisabledReason={isClearing || clearChat.isPending ? 'Очистка в процессе…' : undefined}
          disableClearChat={isClearing || clearChat.isPending}
          clearDisabledReason={isClearing || clearChat.isPending ? 'Очистка в процессе…' : undefined}
          onClearChat={() => {
            closeStreamRef.current?.();
            closeStreamRef.current = null;
            logClientEvent({ event: 'ui.clear_chat.confirmed', notebookId });
            clearChat.mutate();
          }}
          onSaveToNotes={(content) => { logClientEvent({ event: 'ui.note.save_from_chat', notebookId }); createNote.mutate({ title: 'Из чата', content }); }}
        />

        <div
          className="hidden lg:block w-2 cursor-col-resize bg-slate-100 hover:bg-slate-300"
          onMouseDown={() => startResize('right')}
          title="Изменить ширину правой панели"
        />

        <div style={{ width: rightCollapsed ? 44 : rightWidth }} className="h-full shrink-0 bg-white border-l border-slate-200">
          <div className="flex items-center justify-start p-2 border-b border-slate-200">
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs"
              onClick={() => {
                logClientEvent({ event: 'ui.right_panel.toggle', notebookId, metadata: { collapsed: !rightCollapsed } });
                setRightCollapsed((value) => !value);
              }}
              aria-label={rightCollapsed ? 'Развернуть правую панель' : 'Свернуть правую панель'}
            >
              {rightCollapsed ? '⟨' : '⟩'}
            </button>
          </div>
          {!rightCollapsed ? (
            <div className="h-full overflow-auto p-3 space-y-3">
              <EvidencePanel citations={citations} notes={notes.data} sources={sources.data} />
            </div>
          ) : null}
        </div>
      </div>

      {sourceConfigModal ? (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded border p-4 w-[420px] space-y-3">
            <p className="font-semibold">Настройки парсинга: {sourceConfigModal.source.filename}</p>

            <div className="space-y-1 text-sm">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={sourceConfigModal.useGlobalChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalChunkSize: e.target.checked }) : prev)} />Использовать глобальный chunk_size</label>
              <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalChunkSize} value={sourceConfigModal.chunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkSize: e.target.value }) : prev)} />
            </div>

            <div className="space-y-1 text-sm">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={sourceConfigModal.useGlobalOverlap} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOverlap: e.target.checked }) : prev)} />Использовать глобальный chunk_overlap</label>
              <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalOverlap} value={sourceConfigModal.chunkOverlap} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkOverlap: e.target.value }) : prev)} />
            </div>

            <div className="space-y-1 text-sm">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={sourceConfigModal.useGlobalOcrEnabled} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOcrEnabled: e.target.checked }) : prev)} />Использовать глобальный OCR enabled</label>
              <label className="inline-flex items-center gap-2"><input type="checkbox" disabled={sourceConfigModal.useGlobalOcrEnabled} checked={sourceConfigModal.ocrEnabled} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, ocrEnabled: e.target.checked }) : prev)} />Включить OCR</label>
            </div>

            <div className="space-y-1 text-sm">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={sourceConfigModal.useGlobalOcrLanguage} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOcrLanguage: e.target.checked }) : prev)} />Использовать глобальный OCR language</label>
              <input className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalOcrLanguage} value={sourceConfigModal.ocrLanguage} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, ocrLanguage: e.target.value }) : prev)} />
            </div>

            <div className="flex justify-end gap-2">
              <button className="rounded border px-2 py-1 text-xs" onClick={() => setSourceConfigModal(null)}>Отмена</button>
              <button
                className="rounded border px-2 py-1 text-xs"
                onClick={() => {
                  updateSource.mutate(
                    {
                      sourceId: sourceConfigModal.source.id,
                      payload: {
                        individual_config: {
                          chunk_size: sourceConfigModal.useGlobalChunkSize ? null : Number(sourceConfigModal.chunkSize),
                          chunk_overlap: sourceConfigModal.useGlobalOverlap ? null : Number(sourceConfigModal.chunkOverlap),
                          ocr_enabled: sourceConfigModal.useGlobalOcrEnabled ? null : sourceConfigModal.ocrEnabled,
                          ocr_language: sourceConfigModal.useGlobalOcrLanguage ? null : sourceConfigModal.ocrLanguage,
                        },
                      },
                    },
                    {
                      onSuccess: () => {
                        reparseSource.mutate(sourceConfigModal.source.id);
                      },
                    },
                  );
                  setSourceConfigModal(null);
                }}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
