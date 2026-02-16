'use client';

import { Source } from '@/types/dto';
import { api } from '@/lib/api';

export default function DocPreview({ source }: { source: Source | null }) {
  if (!source) return <div className="text-sm text-slate-500">Выберите цитату для предпросмотра.</div>;
  return (
    <div className="border rounded p-3 bg-white">
      <p className="font-medium text-sm">{source.filename}</p>
      <p className="text-xs text-slate-600">{source.file_type} · {source.size_bytes} bytes</p>
      <a className="text-xs text-blue-600 underline" href={api.getFileUrl(source.file_path)} target="_blank">Open file</a>
    </div>
  );
}
