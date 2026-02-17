'use client';

import ChatPanel from '@/components/ChatPanel';
import EvidencePanel from '@/components/EvidencePanel';
import RuntimeSettings from '@/components/RuntimeSettings';
import SourcesPanel from '@/components/SourcesPanel';
import { api, CitationsSchema } from '@/lib/api';
import { ChatMode, openChatStream } from '@/lib/sse';
import { Citation } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

export default function NotebookWorkspacePage() {
  const params = useParams<{ id: string }>();
  const notebookId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<ChatMode>('qa');
  const [streaming, setStreaming] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [explicitSelection, setExplicitSelection] = useState<string[]>([]);

  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const sources = useQuery({ queryKey: ['sources', notebookId], queryFn: () => api.listSources(notebookId) });
  const messages = useQuery({ queryKey: ['messages', notebookId], queryFn: () => api.listMessages(notebookId) });
  const notes = useQuery({ queryKey: ['notes', notebookId], queryFn: () => api.listNotes(notebookId) });

  const createNotebook = useMutation({
    mutationFn: api.createNotebook,
    onSuccess: (notebook) => {
      queryClient.invalidateQueries({ queryKey: ['notebooks'] });
      router.push(`/notebooks/${notebook.id}`);
    },
  });

  const uploadSource = useMutation({
    mutationFn: (file: File) => api.uploadSource(notebookId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', notebookId] }),
  });

  const createNote = useMutation({
    mutationFn: ({ title, content }: { title: string; content: string }) => api.createNote(notebookId, title, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes', notebookId] }),
  });

  const selectedSourceIds = useMemo(() => {
    if (!sources.data) {
      return [];
    }
    return explicitSelection.length > 0 ? explicitSelection : sources.data.map((source) => source.id);
  }, [explicitSelection, sources.data]);

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

  if (notebooks.isLoading || sources.isLoading || messages.isLoading || notes.isLoading) {
    return <div className="p-6">Loading workspace...</div>;
  }
  if (notebooks.isError || sources.isError || messages.isError || notes.isError || !notebooks.data || !sources.data || !messages.data || !notes.data) {
    return <div className="p-6">Failed to load notebook workspace.</div>;
  }

  return (
    <div className="min-h-screen p-3 lg:h-screen">
      <RuntimeSettings />
      <div className="mt-3 lg:flex lg:h-[calc(100%-84px)]">
        <SourcesPanel
          notebooks={notebooks.data}
          activeNotebookId={notebookId}
          sources={sources.data}
          selectedSourceIds={selectedSourceIds}
          onNotebookChange={(id) => router.push(`/notebooks/${id}`)}
          onCreateNotebook={(title) => createNotebook.mutate(title)}
          onToggleSource={(sourceId) =>
            setExplicitSelection((current) =>
              current.includes(sourceId) ? current.filter((id) => id !== sourceId) : [...current, sourceId],
            )
          }
          onUpload={(file) => uploadSource.mutate(file)}
        />

        <ChatPanel
          mode={mode}
          messages={messages.data}
          streaming={streaming}
          citations={citations}
          onModeChange={setMode}
          onSend={sendMessage}
          onSaveToNotes={(content) => createNote.mutate({ title: 'Из чата', content })}
        />

        <EvidencePanel citations={citations} notes={notes.data} sources={sources.data} />
      </div>
    </div>
  );
}
