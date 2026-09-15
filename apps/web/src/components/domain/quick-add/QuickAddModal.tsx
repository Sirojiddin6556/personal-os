'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useUIStore } from '@/stores/ui-store';
import { useParseInput, useQuickAddSubmit } from '@/hooks/useQuickAdd';
import { useTasks } from '@/hooks/useTasks';
import { useNotes } from '@/hooks/useNotes';
import { useProjects } from '@/hooks/useGitHub';
import { TaskPriority } from '@/types/domain';
import { cn } from '@/lib/utils';

export function QuickAddModal() {
  const router = useRouter();
  const { isQuickAddOpen, closeQuickAdd, quickAddInitialType, openTaskDetail } = useUIStore();
  const [inputText, setInputText] = useState('');
  const [selectedIntent, setSelectedIntent] = useState<'task' | 'event' | 'expense' | 'note' | 'search'>('task');
  const [showStructuredForm, setShowStructuredForm] = useState(false);

  // Fallback structured form fields
  const [manualTitle, setManualTitle] = useState('');
  const [manualPriority, setManualPriority] = useState<TaskPriority>('medium');
  const [manualDate, setManualDate] = useState('');
  const [manualProject, setManualProject] = useState('work');
  const [manualAmount, setManualAmount] = useState('');

  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const { parsed, isParsing } = useParseInput(inputText);
  const { submitQuickAdd, isSubmitting } = useQuickAddSubmit();

  // Search sources
  const { tasks = [] } = useTasks();
  const { notes = [] } = useNotes();
  const { data: dbProjects = [] } = useProjects();

  const searchResults = useMemo(() => {
    const q = inputText.trim().toLowerCase();
    if (!q || q.length < 2) return { tasks: [], notes: [], projects: [] };

    const matchedTasks = tasks.filter((t) => t.title.toLowerCase().includes(q)).slice(0, 4);
    const matchedNotes = notes.filter((n) => n.title.toLowerCase().includes(q) || (n.content_markdown || '').toLowerCase().includes(q)).slice(0, 4);
    const matchedProjects = dbProjects.filter((p: any) => (p.name || p.title || '').toLowerCase().includes(q)).slice(0, 3);

    return { tasks: matchedTasks, notes: matchedNotes, projects: matchedProjects };
  }, [inputText, tasks, notes, dbProjects]);

  const totalResultsCount = searchResults.tasks.length + searchResults.notes.length + searchResults.projects.length;

  // Reset when opened
  useEffect(() => {
    if (isQuickAddOpen) {
      setInputText('');
      setSelectedIntent((quickAddInitialType as any) || 'task');
      setShowStructuredForm(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isQuickAddOpen, quickAddInitialType]);

  // Sync detected intent from NLP
  useEffect(() => {
    if (parsed && !showStructuredForm && selectedIntent !== 'search') {
      setSelectedIntent(parsed.intent);
    }
  }, [parsed, showStructuredForm, selectedIntent]);

  if (!isQuickAddOpen) return null;

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (selectedIntent === 'search') return;

    const title = showStructuredForm ? manualTitle : (parsed?.title || inputText);
    if (!title.trim() && !manualAmount && selectedIntent !== 'expense') return;

    try {
      await submitQuickAdd({
        intent: selectedIntent as any,
        title: title.trim() || (selectedIntent === 'expense' ? 'Расход' : 'Новый элемент'),
        priority: showStructuredForm ? manualPriority : (parsed?.priority || 'medium'),
        dueDate: showStructuredForm ? manualDate : parsed?.due_date,
        isoDate: parsed?.iso_date,
        project: showStructuredForm ? manualProject : parsed?.project,
        amount: showStructuredForm ? parseFloat(manualAmount) : parsed?.amount,
        currency: parsed?.currency || 'UZS',
        noteContent: title,
      });
      closeQuickAdd();
    } catch (err) {
      console.error('Failed to quick add:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeQuickAdd();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="quick-add-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeQuickAdd();
      }}
    >
      <div className="relative w-full max-w-xl bg-surface border border-border rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Top Bar: Auto-detected entity intent chips */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5 border-b border-border-subtle bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-1.5" role="tablist">
            {(['task', 'event', 'expense', 'note', 'search'] as const).map((intent) => {
              const labels = { task: 'Задача', event: 'Событие', expense: 'Расход', note: 'Заметка', search: '🔍 Поиск' };
              const isActive = selectedIntent === intent;
              return (
                <button
                  key={intent}
                  type="button"
                  onClick={() => setSelectedIntent(intent)}
                  className={cn(
                    'px-3 py-1 text-xs font-semibold rounded-full transition-all duration-fast',
                    isActive
                      ? 'bg-primary text-white shadow-2xs'
                      : 'text-text-secondary hover:bg-surface-muted hover:text-text-primary'
                  )}
                >
                  {labels[intent]}
                </button>
              );
            })}
          </div>
          <span className="text-[11px] font-mono text-text-muted hidden sm:inline">
            Esc для отмены
          </span>
        </div>

        {/* Body Content */}
        {selectedIntent === 'search' ? (
          /* Universal Global Search View */
          <div className="p-4 sm:p-5 space-y-4">
            <h2 id="quick-add-title" className="sr-only">
              Глобальный поиск
            </h2>
            <div className="relative">
              <textarea
                ref={inputRef}
                rows={1}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Поиск по задачам, заметкам, проектам..."
                className="w-full text-base bg-transparent border-b border-border pb-2 resize-none text-text-primary placeholder:text-text-muted focus:outline-none"
              />
            </div>

            {/* Live Search Results */}
            <div className="max-h-60 overflow-y-auto space-y-3 pt-1">
              {inputText.trim().length >= 2 && totalResultsCount === 0 && (
                <p className="text-center py-4 text-xs text-text-muted">Ничего не найдено по запросу «{inputText}»</p>
              )}

              {/* Tasks */}
              {searchResults.tasks.length > 0 && (
                <div>
                  <span className="text-[11px] font-bold text-text-muted uppercase tracking-wider block mb-1.5">Задачи</span>
                  <div className="space-y-1.5">
                    {searchResults.tasks.map((task) => (
                      <button
                        key={task.id}
                        type="button"
                        onClick={() => {
                          openTaskDetail(task.id);
                          closeQuickAdd();
                        }}
                        className="w-full text-left p-2 rounded-xl bg-surface-muted/60 hover:bg-surface-muted flex items-center justify-between text-xs transition-colors"
                      >
                        <span className="font-medium text-text-primary truncate">📋 {task.title}</span>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-surface border border-border text-text-secondary shrink-0">
                          {task.status}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Notes */}
              {searchResults.notes.length > 0 && (
                <div>
                  <span className="text-[11px] font-bold text-text-muted uppercase tracking-wider block mb-1.5">Заметки</span>
                  <div className="space-y-1.5">
                    {searchResults.notes.map((note) => (
                      <button
                        key={note.id}
                        type="button"
                        onClick={() => {
                          router.push(`/notes/${note.id}`);
                          closeQuickAdd();
                        }}
                        className="w-full text-left p-2 rounded-xl bg-surface-muted/60 hover:bg-surface-muted flex items-center justify-between text-xs transition-colors"
                      >
                        <span className="font-medium text-text-primary truncate">📝 {note.title}</span>
                        <span className="text-[10px] text-text-muted shrink-0">Заметка</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Projects */}
              {searchResults.projects.length > 0 && (
                <div>
                  <span className="text-[11px] font-bold text-text-muted uppercase tracking-wider block mb-1.5">Проекты</span>
                  <div className="space-y-1.5">
                    {searchResults.projects.map((proj: any) => (
                      <button
                        key={proj.id}
                        type="button"
                        onClick={() => {
                          router.push(`/projects`);
                          closeQuickAdd();
                        }}
                        className="w-full text-left p-2 rounded-xl bg-surface-muted/60 hover:bg-surface-muted flex items-center justify-between text-xs transition-colors"
                      >
                        <span className="font-medium text-text-primary truncate">📁 {proj.name || proj.title}</span>
                        <span className="text-[10px] text-text-muted shrink-0">Проект</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : !showStructuredForm ? (
          /* Fast NLP Free-text Mode (Quick Add <= 3 actions) */
          <div className="p-4 sm:p-5">
            <h2 id="quick-add-title" className="sr-only">
              Быстрое добавление
            </h2>
            <textarea
              ref={inputRef}
              rows={2}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Что нужно сделать? (например: 'Подготовить отчёт до пятницы #work !high')"
              className="w-full text-base bg-transparent border-0 resize-none text-text-primary placeholder:text-text-muted focus:outline-none leading-relaxed"
            />

            {/* Live AI Preview card */}
            {inputText.trim() && (
              <div className="mt-3 p-3 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800/60 text-xs flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1.5 font-bold text-indigo-700 dark:text-indigo-300">
                  {isParsing ? (
                    <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" strokeWidth="4" className="opacity-25" />
                      <path fill="currentColor" d="M4 12a8 8 0 018-8v8z" className="opacity-75" />
                    </svg>
                  ) : (
                    <span>✨</span>
                  )}
                  <span>Распознано:</span>
                </div>

                {parsed?.due_date && (
                  <span className="px-2 py-0.5 rounded bg-surface border border-indigo-200 dark:border-indigo-800 font-medium text-text-primary">
                    📅 {parsed.due_date}
                  </span>
                )}

                {parsed?.project && (
                  <span className="px-2 py-0.5 rounded bg-surface border border-indigo-200 dark:border-indigo-800 font-medium text-indigo-600 dark:text-indigo-400">
                    📁 #{parsed.project}
                  </span>
                )}

                {parsed?.priority && (
                  <span
                    className={cn(
                      'px-2 py-0.5 rounded font-bold uppercase text-[10px]',
                      parsed.priority === 'critical'
                        ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                        : parsed.priority === 'high'
                        ? 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300'
                        : 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300'
                    )}
                  >
                    !{parsed.priority}
                  </span>
                )}

                {parsed?.amount !== undefined && (
                  <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-bold font-mono">
                    💰 {parsed.amount.toLocaleString()} {parsed.currency}
                  </span>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Fallback Structured Form */
          <div className="p-4 sm:p-5 space-y-3">
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1">
                Название
              </label>
              <input
                type="text"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                placeholder="Название задачи или события"
                className="w-full px-3 py-2 text-sm bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  Приоритет
                </label>
                <select
                  value={manualPriority}
                  onChange={(e) => setManualPriority(e.target.value as TaskPriority)}
                  className="w-full px-3 py-2 text-sm bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="low">Низкий (Low)</option>
                  <option value="medium">Средний (Medium)</option>
                  <option value="high">Высокий (High)</option>
                  <option value="critical">Критический (Critical)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  Проект
                </label>
                <input
                  type="text"
                  value={manualProject}
                  onChange={(e) => setManualProject(e.target.value)}
                  placeholder="work / personal"
                  className="w-full px-3 py-2 text-sm bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            {selectedIntent === 'expense' && (
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  Сумма (UZS / сум)
                </label>
                <input
                  type="number"
                  value={manualAmount}
                  onChange={(e) => setManualAmount(e.target.value)}
                  placeholder="45000"
                  className="w-full px-3 py-2 text-sm bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-primary font-mono"
                />
              </div>
            )}
          </div>
        )}

        {/* Footer with Submit CTA */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900 border-t border-border">
          <div className="flex items-center gap-2">
            {selectedIntent !== 'search' && (
              <button
                type="button"
                onClick={() => setShowStructuredForm(!showStructuredForm)}
                className="text-xs text-primary hover:underline font-medium"
              >
                {showStructuredForm ? '← Быстрый ввод' : 'Подробные поля'}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={closeQuickAdd}
              className="px-3.5 py-1.5 text-xs font-semibold text-text-secondary hover:bg-surface-muted rounded-md transition-colors"
            >
              Отмена
            </button>
            {selectedIntent !== 'search' && (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => handleSubmit()}
                className="px-4 py-1.5 text-xs font-bold text-white bg-primary hover:bg-primary-600 active:scale-95 disabled:opacity-50 rounded-md shadow-sm transition-all"
              >
                {isSubmitting ? 'Сохранение...' : 'Создать [Enter]'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default QuickAddModal;
