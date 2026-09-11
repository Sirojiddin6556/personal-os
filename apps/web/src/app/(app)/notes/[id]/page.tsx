'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useNote, useUpdateNote, useNoteSearch } from '@/hooks/useNotes';
import { formatDateShort } from '@/lib/utils';
import Link from 'next/link';

// Dynamically import MDEditor with SSR disabled
const MDEditor = dynamic(
  () => import('@uiw/react-md-editor').then((mod) => mod.default),
  {
    ssr: false,
    loading: () => (
      <div className="h-96 w-full rounded-xl bg-surface-muted animate-pulse flex items-center justify-center text-xs text-text-muted">
        Загрузка редактора Markdown...
      </div>
    ),
  }
);

export default function NoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = (params?.id as string) || '';

  const { note, isLoading, isError, error } = useNote(id);
  const updateNoteMutation = useUpdateNote(id);

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'dirty' | 'error'>('saved');
  const [ragQuery, setRagQuery] = useState('');
  const [isRagOpen, setIsRagOpen] = useState(false);

  const { results: searchResults, isLoading: isSearchLoading } = useNoteSearch(ragQuery);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initialize values when note loads
  useEffect(() => {
    if (note) {
      setTitle(note.title);
      setContent(note.content_markdown || '');
    }
  }, [note]);

  // Debounced auto-save function (1000ms delay)
  const triggerAutoSave = useCallback(
    (newTitle: string, newContent: string) => {
      setSaveStatus('dirty');

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(async () => {
        setSaveStatus('saving');
        try {
          await updateNoteMutation.mutateAsync({
            title: newTitle,
            content_markdown: newContent,
          });
          setSaveStatus('saved');
        } catch (err) {
          console.error('Failed to auto-save note:', err);
          setSaveStatus('error');
        }
      }, 1000);
    },
    [updateNoteMutation]
  );

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setTitle(val);
    triggerAutoSave(val, content);
  };

  const handleContentChange = (val?: string) => {
    const newContent = val ?? '';
    setContent(newContent);
    triggerAutoSave(title, newContent);
  };

  const handleInsertWikiLink = (linkedTitle: string, linkedId: string) => {
    const linkText = `[[${linkedTitle}]]`;
    const newContent = content ? `${content}\n\n${linkText}` : linkText;
    setContent(newContent);
    triggerAutoSave(title, newContent);
  };

  if (isLoading) {
    return (
      <div className="flex h-96 w-full items-center justify-center text-text-muted">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="text-xs font-medium">Загрузка заметки...</span>
        </div>
      </div>
    );
  }

  if (isError || !note) {
    return (
      <div className="p-8 max-w-2xl mx-auto text-center space-y-4">
        <div className="p-4 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-sm">
          {error?.message || 'Заметка не найдена или была удалена.'}
        </div>
        <button
          onClick={() => router.back()}
          className="px-4 py-2 rounded-xl bg-primary text-white text-xs font-semibold"
        >
          ← Вернуться назад
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between gap-4 pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            aria-label="Назад"
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-muted transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-500">
                Заметка
              </span>
              <span className="text-xs text-text-muted">•</span>
              <span className="text-xs text-text-muted">
                {formatDateShort(note.updated_at || note.created_at || new Date().toISOString())}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-save Status Indicator */}
          <div className="flex items-center gap-1.5 text-xs">
            {saveStatus === 'saving' && (
              <>
                <div className="w-2 h-2 rounded-full bg-status-warning animate-ping" />
                <span className="text-text-muted">Сохранение...</span>
              </>
            )}
            {saveStatus === 'saved' && (
              <>
                <div className="w-2 h-2 rounded-full bg-status-success" />
                <span className="text-text-muted">Сохранено</span>
              </>
            )}
            {saveStatus === 'dirty' && (
              <>
                <div className="w-2 h-2 rounded-full bg-status-warning" />
                <span className="text-text-muted">Есть правки...</span>
              </>
            )}
            {saveStatus === 'error' && (
              <>
                <div className="w-2 h-2 rounded-full bg-status-error" />
                <span className="text-status-error font-medium">Ошибка сохранения</span>
              </>
            )}
          </div>

          {/* RAG Search Toggle Button */}
          <button
            onClick={() => setIsRagOpen(!isRagOpen)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              isRagOpen
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400'
                : 'bg-surface border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span>RAG Поиск</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Editor Main Column */}
        <div className={isRagOpen ? 'lg:col-span-3 space-y-4' : 'lg:col-span-4 space-y-4'}>
          {/* Note Title Input */}
          <input
            type="text"
            value={title}
            onChange={handleTitleChange}
            placeholder="Заголовок заметки..."
            className="w-full text-2xl font-bold bg-transparent border-none text-text-primary placeholder:text-text-muted focus:outline-none px-1"
          />

          {/* Markdown Editor */}
          <div data-color-mode="auto" className="rounded-xl overflow-hidden border border-border">
            <MDEditor
              value={content}
              onChange={handleContentChange}
              preview="live"
              height={550}
              textareaProps={{
                placeholder: 'Пишите в формате Markdown... Используйте [[WikiLinks]] для связывания заметок.',
              }}
            />
          </div>
        </div>

        {/* RAG Knowledge Search Sidebar */}
        {isRagOpen && (
          <div className="lg:col-span-1 bg-surface border border-border rounded-xl p-4 space-y-4 h-fit animate-slide-in">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-text-primary flex items-center gap-1.5">
                <svg className="w-4 h-4 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                </svg>
                <span>AI RAG Контекст</span>
              </h3>
              <button
                onClick={() => setIsRagOpen(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded"
              >
                ✕
              </button>
            </div>

            {/* Query Input */}
            <div className="relative">
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Поиск по базе знаний..."
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-surface-muted border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Results List */}
            <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
              {isSearchLoading ? (
                <div className="text-center py-4 text-xs text-text-muted animate-pulse">
                  Идет семантический поиск...
                </div>
              ) : searchResults.length > 0 ? (
                searchResults.map((result) => (
                  <div
                    key={result.note_id}
                    className="p-2.5 rounded-lg bg-surface-muted border border-border/80 hover:border-primary/40 space-y-1 transition-all"
                  >
                    <div className="flex items-center justify-between text-xs font-semibold text-text-primary">
                      <span className="truncate">{result.title}</span>
                      <span className="text-[10px] text-amber-500 font-mono">
                        {Math.round(result.score * 100)}%
                      </span>
                    </div>
                    <p className="text-[11px] text-text-muted line-clamp-2">
                      {result.snippet}
                    </p>
                    <div className="pt-1 flex items-center justify-between text-[10px]">
                      <button
                        onClick={() => handleInsertWikiLink(result.title, result.note_id)}
                        className="text-primary hover:underline font-medium"
                      >
                        + Вставить [[WikiLink]]
                      </button>
                      <Link
                        href={`/notes/${result.note_id}`}
                        className="text-text-muted hover:text-text-primary"
                      >
                        Открыть ↗
                      </Link>
                    </div>
                  </div>
                ))
              ) : ragQuery ? (
                <div className="text-center py-4 text-xs text-text-muted">
                  Ничего не найдено
                </div>
              ) : (
                <div className="text-center py-4 text-xs text-text-muted">
                  Введите запрос для семантического поиска по всем заметкам базы знаний.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
