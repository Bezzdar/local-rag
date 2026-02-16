'use client';

import { api } from '@/lib/api';
import { Source } from '@/types/dto';

export default function DocPreview({ source }: { source: Source | null }) {
  if (!source) {
    return <div className="rounded border border-slate-200 p-3 text-sm text-slate-500">Выберите цитату для предпросмотра.</div>;
  }

  return (
    <div className="rounded border border-slate-200 bg-white p-3 space-y-1">
      <p className="text-sm font-medium break-all">{source.filename}</p>
      <p className="text-xs text-slate-600">{source.file_type} · {source.size_bytes} bytes</p>
      <a className="text-xs text-blue-600 underline" href={api.fileUrl(source.file_path)} target="_blank" rel="noreferrer">
        Open file
      </a>
    </div>
  );
}
