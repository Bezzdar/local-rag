'use client';

import ChatPanel from '@/components/ChatPanel';
import EvidencePanel from '@/components/EvidencePanel';
import SourcesPanel from '@/components/SourcesPanel';
import { api, CitationsSchema } from '@/lib/api';
import { streamChat } from '@/lib/sse';
import { Citation } from '@/types/dto';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function NotebookWorkspacePage() {
  const params = useParams<{ id: string }>();
  const notebookId = params.id;
  const qc = useQueryClient();
  const router = useRouter();

  const [mode, setMode] = useState<'qa' | 'draft' | 'table' | 'summarize'>('qa');
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);

  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: api.listNotebooks });
  const sources = useQuery({ queryKey: ['sources', notebookId], queryFn: () => api.listSources(notebookId) });
  const messages = useQuery({ queryKey: ['messages', notebookId], queryFn: () => api.listMessages(notebookId) });
  const notes = useQuery({ queryKey: ['notes', notebookId], queryFn: () => api.listNotes(notebookId) });

  const createNotebook = useMutation({ mutationFn: api.createNotebook, onSuccess: (n) => qc.invalidateQueries({ queryKey: ['notebooks'] }).then(() => router.push(`/notebooks/${n.id}`)) });
  const upload = useMutation({ mutationFn: (file: File) => api.uploadSource(notebookId, file), onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', notebookId] }) });
  const createNote = useMutation({ mutationFn: ({ title, content }: { title: string; content: string }) => api.createNote(notebookId, title, content), onSuccess: () => qc.invalidateQueries({ queryKey: ['notes', notebookId] }) });

  const allLoaded = notebooks.data && sources.data && messages.data && notes.data;

  const sendMessage = (text: string) => {
    setStreamingText('');
    const close = streamChat({
      notebookId,
      message: text,
      mode,
      selectedSourceIds,
      events: {
        onToken: (token) => setStreamingText((s) => s + token),
        onCitations: (raw) => setCitations(CitationsSchema.parse(raw)),
        onDone: () => { qc.invalidateQueries({ queryKey: ['messages', notebookId] }); setStreamingText(''); close(); },
        onError: () => close(),
      },
    });
  };

  if (!allLoaded) return <div className="p-6">Loading...</div>;

  return (
    <div className="min-h-screen lg:h-screen lg:flex">
      <SourcesPanel
        notebooks={notebooks.data}
        activeNotebookId={notebookId}
        sources={sources.data}
        selectedSourceIds={selectedSourceIds.length ? selectedSourceIds : sources.data.map((s) => s.id)}
        onNotebookChange={(id) => router.push(`/notebooks/${id}`)}
        onCreateNotebook={(title) => createNotebook.mutate(title)}
        onToggleSource={(id) => setSelectedSourceIds((prev) => prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id])}
        onUpload={(file) => upload.mutate(file)}
      />
      <ChatPanel
        messages={messages.data}
        streamingText={streamingText}
        mode={mode}
        onModeChange={setMode}
        onSend={sendMessage}
        onSaveToNotes={(content) => createNote.mutate({ title: 'Из чата', content })}
        citations={citations}
      />
      <EvidencePanel citations={citations} notes={notes.data} sources={sources.data} />
    </div>
  );
}
