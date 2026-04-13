'use client';

import { api, clearAuthToken, saveAuthToken } from '@/lib/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

export default function ArticlesPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const me = useQuery({ queryKey: ['me'], queryFn: api.me, retry: false });
  const articles = useQuery({ queryKey: ['articles'], queryFn: api.listArticles, enabled: me.isSuccess });

  const register = useMutation({
    mutationFn: api.register,
    onSuccess: (data) => {
      saveAuthToken(data.access_token);
      queryClient.invalidateQueries({ queryKey: ['me'] });
    },
    onError: (err) => setError(String(err)),
  });

  const login = useMutation({
    mutationFn: api.login,
    onSuccess: (data) => {
      saveAuthToken(data.access_token);
      queryClient.invalidateQueries({ queryKey: ['me'] });
    },
    onError: (err) => setError(String(err)),
  });

  const createArticle = useMutation({
    mutationFn: api.createArticle,
    onSuccess: () => {
      setTitle('');
      setSummary('');
      setContent('');
      queryClient.invalidateQueries({ queryKey: ['articles'] });
    },
    onError: (err) => setError(String(err)),
  });

  const updateArticle = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'draft' | 'published' | 'archived' }) => api.updateArticle(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['articles'] }),
    onError: (err) => setError(String(err)),
  });

  const isModerator = me.data?.role === 'moderator' || me.data?.role === 'admin';
  const myId = me.data?.user_id;

  const myArticles = useMemo(() => (articles.data ?? []).filter((a) => a.author_id === myId), [articles.data, myId]);

  if (me.isError) {
    return (
      <main className="mx-auto max-w-3xl p-6 space-y-4">
        <h1 className="text-2xl font-semibold">Авторизация и статьи</h1>
        <p className="text-sm text-slate-600">Войдите или зарегистрируйтесь.</p>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <div className="grid gap-2 rounded border bg-white p-4">
          <input className="rounded border px-3 py-2" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className="rounded border px-3 py-2" placeholder="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <input className="rounded border px-3 py-2" placeholder="Имя (для регистрации)" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          <div className="flex gap-2">
            <button className="rounded bg-slate-900 px-3 py-2 text-white" onClick={() => login.mutate({ email, password })}>Войти</button>
            <button className="rounded border px-3 py-2" onClick={() => register.mutate({ email, password, display_name: displayName })}>Регистрация</button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Статьи из БД</h1>
        <button
          className="rounded border px-3 py-2"
          onClick={() => {
            clearAuthToken();
            queryClient.invalidateQueries({ queryKey: ['me'] });
          }}
        >
          Выйти ({me.data?.display_name})
        </button>
      </div>

      <section className="rounded border bg-white p-4 space-y-2">
        <h2 className="font-medium">Добавить свою статью</h2>
        <input className="w-full rounded border px-3 py-2" placeholder="Заголовок" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea className="w-full rounded border px-3 py-2" placeholder="Краткое описание" value={summary} onChange={(e) => setSummary(e.target.value)} rows={3} />
        <textarea className="w-full rounded border px-3 py-2" placeholder="Текст статьи" value={content} onChange={(e) => setContent(e.target.value)} rows={8} />
        <button className="rounded bg-slate-900 px-3 py-2 text-white" onClick={() => createArticle.mutate({ title, summary, content })}>Сохранить черновик</button>
      </section>

      <section className="space-y-3">
        <h2 className="font-medium">Мои статьи</h2>
        {myArticles.map((article) => (
          <article key={article.id} className="rounded border bg-white p-4">
            <div className="text-xs text-slate-500">{article.status} · {new Date(article.updated_at).toLocaleString()}</div>
            <h3 className="font-semibold">{article.title}</h3>
            <p className="text-sm text-slate-700">{article.summary}</p>
          </article>
        ))}
      </section>

      {isModerator ? (
        <section className="space-y-3">
          <h2 className="font-medium">Модерация</h2>
          {(articles.data ?? []).map((article) => (
            <article key={article.id} className="rounded border bg-white p-4 space-y-2">
              <div className="text-xs text-slate-500">Автор: {article.author_name}</div>
              <h3 className="font-semibold">{article.title}</h3>
              <p className="text-sm">{article.summary}</p>
              <div className="flex gap-2 text-sm">
                <button className="rounded border px-2 py-1" onClick={() => updateArticle.mutate({ id: article.id, status: 'published' })}>Опубликовать</button>
                <button className="rounded border px-2 py-1" onClick={() => updateArticle.mutate({ id: article.id, status: 'archived' })}>В архив</button>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </main>
  );
}
