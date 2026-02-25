'use client';

import ChatPanel from '@/components/ChatPanel';
import ConnectionIndicator from '@/components/ConnectionIndicator';
import EvidencePanel from '@/components/EvidencePanel';
import SourcesPanel from '@/components/SourcesPanel';
import { api, CitationsSchema } from '@/lib/api';
import { logClientEvent } from '@/lib/clientLogger';
import { ChatMode, openChatStream } from '@/lib/sse';
import { getRuntimeConfig } from '@/lib/runtime-config';
import { CHUNKING_METHOD_LABELS, CHUNKING_METHODS, Citation, DOC_TYPE_LABELS, DOC_TYPES, GlobalNote, IndividualConfig, SavedCitation, Source } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { beginClear, failClear, finishClear, registerStreamCloser, shouldIgnoreStream, unregisterStreamCloser, useChatStore } from '@/src/stores/chatStore';
import { setKeepAlive } from '@/src/stores/connectionStore';
import { setCurrentMode, useModeStore } from '@/src/stores/modeStore';
import { setSelectedAgent, syncSelectedAgentWithManifest, useAgentStore } from '@/src/stores/agentStore';

const LEFT_MIN = 240;
const LEFT_MAX = 520;
const RIGHT_MIN = 280;
const RIGHT_MAX = 640;

type SourceConfigModalState = {
  source: Source;
  // Chunking method
  useGlobalMethod: boolean;
  chunkingMethod: string;
  // General / Context Enrichment
  useGlobalChunkSize: boolean;
  useGlobalOverlap: boolean;
  chunkSize: string;
  chunkOverlap: string;
  // Context Enrichment
  useGlobalContextWindow: boolean;
  contextWindow: string;
  useGlobalLlmSummary: boolean;
  useLlmSummary: boolean;
  // Hierarchy
  useGlobalDocType: boolean;
  docType: string;
  // PCR
  useGlobalParentChunkSize: boolean;
  parentChunkSize: string;
  useGlobalChildChunkSize: boolean;
  childChunkSize: string;
  // Symbol
  useGlobalSymbolSeparator: boolean;
  symbolSeparator: string;
  // OCR
  useGlobalOcrEnabled: boolean;
  useGlobalOcrLanguage: boolean;
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
  const [messageCitations, setMessageCitations] = useState<Map<string, Citation[]>>(new Map());
  const latestCitationsRef = useRef<Citation[]>([]);
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
  const parsingSettings = useQuery({ queryKey: ['parsing-settings', notebookId], queryFn: () => api.getParsingSettings(notebookId), enabled: allowNotebookQueries });

  // Persistent saved citations (per-notebook)
  const savedCitations = useQuery({
    queryKey: ['saved-citations', notebookId],
    queryFn: () => api.listSavedCitations(notebookId),
    enabled: allowNotebookQueries,
  });

  // Global notes (cross-notebook)
  const globalNotes = useQuery({
    queryKey: ['global-notes'],
    queryFn: () => api.listGlobalNotes(),
    enabled: allowNotebookQueries,
  });


  useEffect(() => {
    if (!agents.data) {
      return;
    }
    syncSelectedAgentWithManifest(agents.data);
  }, [agents.data]);

  const activeNotebook = useMemo(
    () => notebooks.data?.find((nb) => nb.id === notebookId),
    [notebooks.data, notebookId],
  );

  const uploadSource = useMutation({
    mutationFn: (file: File) => api.uploadSource(notebookId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const deleteSources = useMutation({
    mutationFn: (sourceIds: string[]) => Promise.all(sourceIds.map((sourceId) => api.deleteSource(sourceId))),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', notebookId] });
      queryClient.invalidateQueries({ queryKey: ['saved-citations', notebookId] });
    },
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
    mutationFn: ({ sourceId, payload }: { sourceId: string; payload: { is_enabled?: boolean; individual_config?: IndividualConfig } }) => api.updateSource(sourceId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const openSource = useMutation({
    mutationFn: (sourceId: string) => api.openSource(sourceId),
  });

  const reorderSources = useMutation({
    mutationFn: (orderedIds: string[]) => api.reorderSources(notebookId, orderedIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const saveCitation = useMutation({
    mutationFn: (citation: Citation) =>
      api.saveCitation(notebookId, {
        source_id: citation.source_id,
        filename: citation.filename,
        doc_order: citation.doc_order,
        chunk_text: citation.snippet,
        page: citation.location?.page ?? null,
        sheet: citation.location?.sheet ?? null,
        source_notebook_id: notebookId,
        source_type: 'notebook',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-citations', notebookId] });
    },
  });

  const deleteSavedCitation = useMutation({
    mutationFn: (citationId: string) => api.deleteSavedCitation(notebookId, citationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['saved-citations', notebookId] }),
  });

  const saveGlobalNote = useMutation({
    mutationFn: (content: string) =>
      api.createGlobalNote({
        content,
        source_notebook_id: notebookId,
        source_notebook_title: activeNotebook?.title ?? 'Ноутбук',
        source_refs: citations.map((c) => ({ source_id: c.source_id, doc_order: c.doc_order, filename: c.filename })),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['global-notes'] }),
  });

  const deleteGlobalNote = useMutation({
    mutationFn: (noteId: string) => api.deleteGlobalNote(noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['global-notes'] }),
  });

  const clearChat = useMutation({
    mutationFn: () => api.clearMessages(notebookId),
    onMutate: async () => {
      const clearId = beginClear();
      await queryClient.cancelQueries({ queryKey: ['messages', notebookId] });
      queryClient.setQueryData(['messages', notebookId], []);
      setStreaming('');
      setCitations([]);
      setMessageCitations(new Map());
      latestCitationsRef.current = [];
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
    latestCitationsRef.current = [];
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
      agentId: currentMode === 'agent' ? effectiveAgentId : undefined,
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
          const parsed = CitationsSchema.parse(payload);
          setCitations(parsed);
          latestCitationsRef.current = parsed;
        },
        onDone: (messageId) => {
          unregisterStreamCloser(streamId);
          if (!shouldIgnoreStream(streamStartedAt)) {
            if (messageId) {
              const cits = latestCitationsRef.current;
              setMessageCitations((prev) => new Map(prev).set(messageId, cits));
            }
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

  const handleCitationClick = (citation: Citation) => {
    logClientEvent({ event: 'ui.citation.save', notebookId, metadata: { source_id: citation.source_id, doc_order: citation.doc_order } });
    saveCitation.mutate(citation);
  };

  const handleSaveToNotes = (content: string) => {
    logClientEvent({ event: 'ui.note.save_global', notebookId });
    saveGlobalNote.mutate(content);
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

  if (notebooks.isLoading || (allowNotebookQueries && (sources.isLoading || messages.isLoading || parsingSettings.isLoading))) {
    return <div className="p-6">Loading workspace...</div>;
  }
  if (notebooks.isError || (allowNotebookQueries && (sources.isError || messages.isError || parsingSettings.isError))) {
    return <div className="p-6">Failed to load notebook workspace.</div>;
  }
  if (!allowNotebookQueries) {
    return <div className="p-6">Notebook not found. Redirecting…</div>;
  }
  if (!notebooks.data || !sources.data || !messages.data || !parsingSettings.data) {
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
                const cfg = source.individual_config ?? {};
                const gs = parsingSettings.data;
                setSourceConfigModal({
                  source,
                  // Method
                  useGlobalMethod: cfg.chunking_method == null,
                  chunkingMethod: cfg.chunking_method ?? gs.chunking_method,
                  // General
                  useGlobalChunkSize: cfg.chunk_size == null,
                  useGlobalOverlap: cfg.chunk_overlap == null,
                  chunkSize: String(cfg.chunk_size ?? gs.chunk_size),
                  chunkOverlap: String(cfg.chunk_overlap ?? gs.chunk_overlap),
                  // Context Enrichment
                  useGlobalContextWindow: cfg.context_window == null,
                  contextWindow: String(cfg.context_window ?? gs.context_window),
                  useGlobalLlmSummary: cfg.use_llm_summary == null,
                  useLlmSummary: cfg.use_llm_summary ?? gs.use_llm_summary,
                  // Hierarchy
                  useGlobalDocType: cfg.doc_type == null,
                  docType: cfg.doc_type ?? gs.doc_type,
                  // PCR
                  useGlobalParentChunkSize: cfg.parent_chunk_size == null,
                  parentChunkSize: String(cfg.parent_chunk_size ?? gs.parent_chunk_size),
                  useGlobalChildChunkSize: cfg.child_chunk_size == null,
                  childChunkSize: String(cfg.child_chunk_size ?? gs.child_chunk_size),
                  // Symbol
                  useGlobalSymbolSeparator: cfg.symbol_separator == null,
                  symbolSeparator: cfg.symbol_separator ?? gs.symbol_separator,
                  // OCR
                  useGlobalOcrEnabled: cfg.ocr_enabled == null,
                  useGlobalOcrLanguage: cfg.ocr_language == null,
                  ocrEnabled: cfg.ocr_enabled ?? gs.ocr_enabled,
                  ocrLanguage: cfg.ocr_language ?? gs.ocr_language,
                });
              }}
              onOpenSource={(source) => {
                logClientEvent({ event: 'ui.source.open', notebookId, metadata: { sourceId: source.id, filename: source.filename } });
                openSource.mutate(source.id);
              }}
              onReorderSources={(orderedIds) => {
                logClientEvent({ event: 'ui.sources.reorder', notebookId, metadata: { count: orderedIds.length } });
                reorderSources.mutate(orderedIds);
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
          agentId={effectiveAgentId}
          agents={agents.data ?? []}
          agentsLoading={agents.isLoading}
          agentsError={agents.isError ? 'Не удалось загрузить манифест агентов.' : ''}
          messages={messages.data}
          streaming={streaming}
          citations={citations}
          messageCitations={messageCitations}
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
          onSaveToNotes={handleSaveToNotes}
          onCitationClick={handleCitationClick}
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
              <EvidencePanel
                savedCitations={savedCitations.data ?? []}
                globalNotes={globalNotes.data ?? []}
                sources={sources.data}
                onDeleteCitation={(citation: SavedCitation) => {
                  logClientEvent({ event: 'ui.citation.delete', notebookId, metadata: { id: citation.id } });
                  deleteSavedCitation.mutate(citation.id);
                }}
                onDeleteNote={(note: GlobalNote) => {
                  logClientEvent({ event: 'ui.note.delete', notebookId, metadata: { id: note.id } });
                  deleteGlobalNote.mutate(note.id);
                }}
                onOpenSource={(sourceId) => {
                  logClientEvent({ event: 'ui.source.open', notebookId, metadata: { sourceId } });
                  openSource.mutate(sourceId);
                }}
              />
            </div>
          ) : null}
        </div>
      </div>

      {sourceConfigModal ? (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded border p-4 w-[460px] max-h-[90vh] overflow-y-auto space-y-3">
            <p className="font-semibold text-sm">Настройки парсинга: {sourceConfigModal.source.filename}</p>

            {/* Method */}
            <div className="space-y-1 text-sm border-b pb-3">
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={sourceConfigModal.useGlobalMethod} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalMethod: e.target.checked }) : prev)} />
                <span className="text-xs">Глобальный метод</span>
              </label>
              <select
                className="w-full rounded border p-1 text-xs"
                disabled={sourceConfigModal.useGlobalMethod}
                value={sourceConfigModal.chunkingMethod}
                onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkingMethod: e.target.value }) : prev)}
              >
                {CHUNKING_METHODS.map((m) => (
                  <option key={m} value={m}>{CHUNKING_METHOD_LABELS[m]}</option>
                ))}
              </select>
            </div>

            {/* Effective method for showing fields */}
            {(() => {
              const effectiveMethod = sourceConfigModal.useGlobalMethod
                ? parsingSettings.data.chunking_method
                : sourceConfigModal.chunkingMethod;

              return (
                <div className="space-y-2">
                  {/* General & Context Enrichment: chunk_size + overlap */}
                  {(effectiveMethod === 'general' || effectiveMethod === 'context_enrichment') && (
                    <>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalChunkSize: e.target.checked }) : prev)} />
                          Глобальный chunk size
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalChunkSize} value={sourceConfigModal.chunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkSize: e.target.value }) : prev)} />
                      </div>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalOverlap} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOverlap: e.target.checked }) : prev)} />
                          Глобальный overlap
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalOverlap} value={sourceConfigModal.chunkOverlap} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkOverlap: e.target.value }) : prev)} />
                      </div>
                    </>
                  )}

                  {/* Context Enrichment extras */}
                  {effectiveMethod === 'context_enrichment' && (
                    <>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalContextWindow} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalContextWindow: e.target.checked }) : prev)} />
                          Глобальный context window
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalContextWindow} value={sourceConfigModal.contextWindow} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, contextWindow: e.target.value }) : prev)} />
                      </div>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalLlmSummary} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalLlmSummary: e.target.checked }) : prev)} />
                          Глобальный LLM summary
                        </label>
                        <label className="inline-flex items-center gap-2 pl-6">
                          <input type="checkbox" disabled={sourceConfigModal.useGlobalLlmSummary} checked={sourceConfigModal.useLlmSummary} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useLlmSummary: e.target.checked }) : prev)} />
                          LLM-суммаризация
                        </label>
                      </div>
                    </>
                  )}

                  {/* Hierarchy */}
                  {effectiveMethod === 'hierarchy' && (
                    <>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalDocType} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalDocType: e.target.checked }) : prev)} />
                          Глобальный тип документа
                        </label>
                        <select
                          className="w-full rounded border p-1 text-xs"
                          disabled={sourceConfigModal.useGlobalDocType}
                          value={sourceConfigModal.docType}
                          onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, docType: e.target.value }) : prev)}
                        >
                          {DOC_TYPES.map((t) => (
                            <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalChunkSize: e.target.checked }) : prev)} />
                          Глобальный chunk size (fallback)
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalChunkSize} value={sourceConfigModal.chunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, chunkSize: e.target.value }) : prev)} />
                      </div>
                    </>
                  )}

                  {/* PCR */}
                  {effectiveMethod === 'pcr' && (
                    <>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalParentChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalParentChunkSize: e.target.checked }) : prev)} />
                          Глобальный parent chunk size
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalParentChunkSize} value={sourceConfigModal.parentChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, parentChunkSize: e.target.value }) : prev)} />
                      </div>
                      <div className="space-y-1 text-xs">
                        <label className="inline-flex items-center gap-2">
                          <input type="checkbox" checked={sourceConfigModal.useGlobalChildChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalChildChunkSize: e.target.checked }) : prev)} />
                          Глобальный child chunk size
                        </label>
                        <input type="number" className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalChildChunkSize} value={sourceConfigModal.childChunkSize} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, childChunkSize: e.target.value }) : prev)} />
                      </div>
                    </>
                  )}

                  {/* Symbol */}
                  {effectiveMethod === 'symbol' && (
                    <div className="space-y-1 text-xs">
                      <label className="inline-flex items-center gap-2">
                        <input type="checkbox" checked={sourceConfigModal.useGlobalSymbolSeparator} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalSymbolSeparator: e.target.checked }) : prev)} />
                        Глобальный разделитель
                      </label>
                      <input
                        className="w-full rounded border p-1 font-mono"
                        disabled={sourceConfigModal.useGlobalSymbolSeparator}
                        value={sourceConfigModal.symbolSeparator}
                        onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, symbolSeparator: e.target.value }) : prev)}
                        placeholder="---chunk---"
                      />
                    </div>
                  )}
                </div>
              );
            })()}

            {/* OCR settings */}
            <div className="space-y-2 border-t pt-2">
              <p className="text-xs text-slate-500 font-medium">OCR</p>
              <div className="space-y-1 text-xs">
                <label className="inline-flex items-center gap-2">
                  <input type="checkbox" checked={sourceConfigModal.useGlobalOcrEnabled} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOcrEnabled: e.target.checked }) : prev)} />
                  Глобальный OCR enabled
                </label>
                <label className="inline-flex items-center gap-2 pl-6">
                  <input type="checkbox" disabled={sourceConfigModal.useGlobalOcrEnabled} checked={sourceConfigModal.ocrEnabled} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, ocrEnabled: e.target.checked }) : prev)} />
                  OCR включён
                </label>
              </div>
              <div className="space-y-1 text-xs">
                <label className="inline-flex items-center gap-2">
                  <input type="checkbox" checked={sourceConfigModal.useGlobalOcrLanguage} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, useGlobalOcrLanguage: e.target.checked }) : prev)} />
                  Глобальный язык OCR
                </label>
                <input className="w-full rounded border p-1" disabled={sourceConfigModal.useGlobalOcrLanguage} value={sourceConfigModal.ocrLanguage} onChange={(e) => setSourceConfigModal((prev) => prev ? ({ ...prev, ocrLanguage: e.target.value }) : prev)} />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button className="rounded border px-2 py-1 text-xs" onClick={() => setSourceConfigModal(null)}>Отмена</button>
              <button
                className="rounded border border-blue-300 px-2 py-1 text-xs text-blue-700"
                onClick={() => {
                  const m = sourceConfigModal;
                  updateSource.mutate({
                    sourceId: m.source.id,
                    payload: {
                      individual_config: {
                        chunking_method: m.useGlobalMethod ? null : m.chunkingMethod,
                        chunk_size: m.useGlobalChunkSize ? null : Number(m.chunkSize),
                        chunk_overlap: m.useGlobalOverlap ? null : Number(m.chunkOverlap),
                        context_window: m.useGlobalContextWindow ? null : Number(m.contextWindow),
                        use_llm_summary: m.useGlobalLlmSummary ? null : m.useLlmSummary,
                        doc_type: m.useGlobalDocType ? null : m.docType,
                        parent_chunk_size: m.useGlobalParentChunkSize ? null : Number(m.parentChunkSize),
                        child_chunk_size: m.useGlobalChildChunkSize ? null : Number(m.childChunkSize),
                        symbol_separator: m.useGlobalSymbolSeparator ? null : m.symbolSeparator,
                        ocr_enabled: m.useGlobalOcrEnabled ? null : m.ocrEnabled,
                        ocr_language: m.useGlobalOcrLanguage ? null : m.ocrLanguage,
                      },
                    },
                  });
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
