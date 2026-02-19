'use client';

import ChatPanel from '@/components/ChatPanel';
import EvidencePanel from '@/components/EvidencePanel';
import SourcesPanel from '@/components/SourcesPanel';
import { api, CitationsSchema } from '@/lib/api';
import { ChatMode, openChatStream } from '@/lib/sse';
import { Citation } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

const LEFT_MIN = 240;
const LEFT_MAX = 520;
const RIGHT_MIN = 280;
const RIGHT_MAX = 640;

export default function NotebookWorkspacePage() {
  const params = useParams<{ id: string }>();
  const notebookId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<ChatMode>('rag');
  const [streaming, setStreaming] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [explicitSelection, setExplicitSelection] = useState<string[] | null>(null);

  const [leftWidth, setLeftWidth] = useState(320);
  const [rightWidth, setRightWidth] = useState(360);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const sources = useQuery({ queryKey: ['sources', notebookId], queryFn: () => api.listSources(notebookId) });
  const messages = useQuery({ queryKey: ['messages', notebookId], queryFn: () => api.listMessages(notebookId) });
  const notes = useQuery({ queryKey: ['notes', notebookId], queryFn: () => api.listNotes(notebookId) });

  const uploadSource = useMutation({
    mutationFn: (file: File) => api.uploadSource(notebookId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const deleteSources = useMutation({
    mutationFn: (sourceIds: string[]) => Promise.all(sourceIds.map((sourceId) => api.deleteSource(sourceId))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const createNote = useMutation({
    mutationFn: ({ title, content }: { title: string; content: string }) => api.createNote(notebookId, title, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes', notebookId] }),
  });

  const clearChat = useMutation({
    mutationFn: () => api.clearMessages(notebookId),
    onSuccess: () => {
      setStreaming('');
      setCitations([]);
      queryClient.invalidateQueries({ queryKey: ['messages', notebookId] });
    },
  });

  const allSourceIds = useMemo(() => sources.data?.map((source) => source.id) ?? [], [sources.data]);

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

  const sendMessage = (text: string) => {
    setStreaming('');
    const close = openChatStream({
      notebookId,
      message: text,
      mode,
      selectedSourceIds,
      handlers: {
        onToken: (token) => setStreaming((value) => value + token),
        onCitations: (payload) => setCitations(CitationsSchema.parse(payload)),
        onDone: () => {
          queryClient.invalidateQueries({ queryKey: ['messages', notebookId] });
          setStreaming('');
          close();
        },
        onError: () => close(),
      },
    });
  };

  const handleToggleSource = (sourceId: string) => {
    setExplicitSelection((current) => {
      const baseSelection = current ?? allSourceIds;
      return baseSelection.includes(sourceId)
        ? baseSelection.filter((id) => id !== sourceId)
        : [...baseSelection, sourceId];
    });
  };

  const handleDeleteSources = (sourceIds: string[], confirmText: string) => {
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

  if (notebooks.isLoading || sources.isLoading || messages.isLoading || notes.isLoading) {
    return <div className="p-6">Loading workspace...</div>;
  }
  if (notebooks.isError || sources.isError || messages.isError || notes.isError || !notebooks.data || !sources.data || !messages.data || !notes.data) {
    return <div className="p-6">Failed to load notebook workspace.</div>;
  }

  return (
    <div className="min-h-screen p-3 lg:h-screen">
      <div className="mt-3 flex h-[calc(100%-84px)]">
        <div style={{ width: leftCollapsed ? 44 : leftWidth }} className="h-full shrink-0 bg-white border-r border-slate-200">
          <div className="flex items-center justify-end p-2 border-b border-slate-200">
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs"
              onClick={() => setLeftCollapsed((value) => !value)}
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
              onSelectAllSources={() => setExplicitSelection(allSourceIds)}
              onClearSourceSelection={() => setExplicitSelection([])}
              onDeleteAllSources={() => handleDeleteSources(allSourceIds, 'Удалить все документы?')}
              onDeleteUnselectedSources={() =>
                handleDeleteSources(
                  allSourceIds.filter((sourceId) => !selectedSourceIds.includes(sourceId)),
                  'Удалить все невыбранные документы?',
                )
              }
              onUpload={(file) => uploadSource.mutate(file)}
            />
          ) : null}
        </div>

        <div
          className="hidden lg:block w-2 cursor-col-resize bg-slate-100 hover:bg-slate-300"
          onMouseDown={() => startResize('left')}
          title="Изменить ширину левой панели"
        />

        <ChatPanel
          mode={mode}
          messages={messages.data}
          streaming={streaming}
          citations={citations}
          onModeChange={setMode}
          onSend={sendMessage}
          onClearChat={() => clearChat.mutate()}
          onSaveToNotes={(content) => createNote.mutate({ title: 'Из чата', content })}
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
              onClick={() => setRightCollapsed((value) => !value)}
              aria-label={rightCollapsed ? 'Развернуть правую панель' : 'Свернуть правую панель'}
            >
              {rightCollapsed ? '⟨' : '⟩'}
            </button>
          </div>
          {!rightCollapsed ? <EvidencePanel citations={citations} notes={notes.data} sources={sources.data} /> : null}
        </div>
      </div>
    </div>
  );
}
