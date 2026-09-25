'use client';
import React, { useState, useEffect } from 'react';
import { useTask, useUpdateTask, useCompleteTask, useDeleteTask } from '@/hooks/useTasks';
import { useUIStore } from '@/stores/ui-store';
import { TaskStatus, Priority } from '@/types/domain';
import { cn } from '@/lib/utils';
import { TaskAttachmentsSection } from './TaskAttachmentsSection';

export function TaskDetailPanel({ taskId }: { taskId: string }) {
  const { task, isLoading, isError, error } = useTask(taskId);
  const updateTaskMutation = useUpdateTask();
  const completeTaskMutation = useCompleteTask();
  const deleteTaskMutation = useDeleteTask();
  const { closeTaskDetail, closeRightPanel } = useUIStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<string>('inbox');
  const [priority, setPriority] = useState<string>('medium');
  const [dueDate, setDueDate] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('');
  const [localSubtasks, setLocalSubtasks] = useState<Array<{ id: string; title: string; completed: boolean }>>([]);



  useEffect(() => {
    if (task) {
      setTitle(task.title || '');
      setDescription(task.description_markdown ?? task.description ?? '');
      setStatus(task.status || 'inbox');
      setPriority(task.priority || 'medium');
      const rawDue = task.due_at || task.due_date;
      setDueDate(rawDue ? rawDue.split('T')[0] : '');
      const subs = (task.subtasks || []).map((s) => ({
        id: s.id,
        title: s.title,
        completed: Boolean(s.is_completed || s.completed),
      }));
      setLocalSubtasks(subs);
    }
  }, [task]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-text-muted">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" strokeWidth="3" className="opacity-25" />
            <path d="M4 12a8 8 0 018-8" strokeWidth="3" className="opacity-75" />
          </svg>
          <span>Загрузка данных задачи…</span>
        </div>
      </div>
    );
  }

  if (isError || !task) {
    return (
      <div className="space-y-3 p-4 text-sm">
        <p className="text-rose-600 dark:text-rose-400 font-semibold">Не удалось загрузить задачу.</p>
        {error?.message && <p className="text-xs text-text-muted">{error.message}</p>}
      </div>
    );
  }

  const isCompleted = status === TaskStatus.DONE;
  const currentVersion = task.version ?? 1;

  const handleSaveFields = async (patch: {
    title?: string;
    description?: string;
    status?: TaskStatus;
    priority?: Priority;
    due_at?: string | null;
  }) => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await updateTaskMutation.mutateAsync({
        id: task.id,
        version: currentVersion,
        ...patch,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      console.error('Failed to update task:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleComplete = async () => {
    const nextStatus = isCompleted ? TaskStatus.TODO : TaskStatus.DONE;
    setStatus(nextStatus);
    try {
      await completeTaskMutation.mutateAsync({
        id: task.id,
        version: currentVersion,
        status: nextStatus,
      });
    } catch (err) {
      console.error('Failed to toggle task completion:', err);
    }
  };

  const handleDelete = async () => {
    if (window.confirm(`Удалить задачу "${task.title}"?`)) {
      try {
        await deleteTaskMutation.mutateAsync({
          id: task.id,
          version: currentVersion,
        });
        closeTaskDetail();
        closeRightPanel();
      } catch (err) {
        console.error('Failed to delete task:', err);
      }
    }
  };

  const handleAddSubtask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubtaskTitle.trim()) return;
    const newSub = {
      id: `sub-${Date.now()}`,
      title: newSubtaskTitle.trim(),
      completed: false,
    };
    setLocalSubtasks((prev) => [...prev, newSub]);
    setNewSubtaskTitle('');
  };

  const handleToggleSubtask = (subId: string) => {
    setLocalSubtasks((prev) =>
      prev.map((s) => (s.id === subId ? { ...s, completed: !s.completed } : s))
    );
  };

  const handleDeleteSubtask = (subId: string) => {
    setLocalSubtasks((prev) => prev.filter((s) => s.id !== subId));
  };

  return (
    <article className="space-y-5 pb-8" data-testid="task-detail-panel">
      {/* 1. Header with Status Toggle & Version Info */}
      <div className="flex items-center justify-between gap-2 pb-2 border-b border-border">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleToggleComplete}
            className={cn(
              'px-2.5 py-1 text-xs font-semibold rounded-lg border transition-colors flex items-center gap-1.5',
              isCompleted
                ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800'
                : 'bg-surface-muted text-text-secondary border-border hover:bg-surface hover:text-text-primary'
            )}
          >
            <span className="text-sm">{isCompleted ? '✓' : '○'}</span>
            <span>{isCompleted ? 'Выполнено' : 'Отметить выполненной'}</span>
          </button>
          {isSaving && <span className="text-[11px] text-text-muted animate-pulse">Сохранение…</span>}
          {saveSuccess && <span className="text-[11px] text-emerald-600 font-medium">Сохранено ✓</span>}
        </div>

        <span className="text-[10px] text-text-muted font-mono">v{task.version ?? 1}</span>
      </div>

      {/* 2. Editable Title */}
      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider text-text-muted mb-1">
          Название
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => {
            if (title.trim() && title !== task.title) {
              handleSaveFields({ title: title.trim() });
            }
          }}
          placeholder="Название задачи"
          className="w-full px-3 py-2 text-sm font-semibold text-text-primary bg-surface-muted hover:bg-surface focus:bg-surface border border-border focus:border-primary rounded-lg transition-colors focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* 3. Status & Priority Selectors */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-text-muted mb-1">
            Статус
          </label>
          <select
            value={status}
            onChange={(e) => {
              const val = e.target.value;
              setStatus(val);
              handleSaveFields({ status: val as TaskStatus });
            }}
            className="w-full px-2.5 py-1.5 text-xs text-text-primary bg-surface-muted border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
          >
            <option value="inbox">📥 Inbox (Входящие)</option>
            <option value="todo">📋 Todo (К выполнению)</option>
            <option value="scheduled">📅 Scheduled (Запланировано)</option>
            <option value="in_progress">⚡ In Progress (В работе)</option>
            <option value="waiting">⏳ Waiting (Ожидание)</option>
            <option value="done">✅ Done (Завершено)</option>
            <option value="cancelled">🚫 Cancelled (Отменено)</option>
            <option value="archived">📦 Archived (В архиве)</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-text-muted mb-1">
            Приоритет
          </label>
          <select
            value={priority}
            onChange={(e) => {
              const val = e.target.value;
              setPriority(val);
              handleSaveFields({ priority: val as Priority });
            }}
            className="w-full px-2.5 py-1.5 text-xs text-text-primary bg-surface-muted border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
          >
            <option value="p1">🔴 P1 (Критический / Urgent)</option>
            <option value="p2">🟠 P2 (Высокий / High)</option>
            <option value="p3">🔵 P3 (Средний / Normal)</option>
            <option value="p4">⚪ P4 (Низкий / Someday)</option>
          </select>
        </div>
      </div>

      {/* 4. Due Date */}
      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider text-text-muted mb-1">
          Срок выполнения
        </label>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={dueDate}
            onChange={(e) => {
              const val = e.target.value;
              setDueDate(val);
              handleSaveFields({ due_at: val ? new Date(val).toISOString() : null });
            }}
            className="flex-1 px-3 py-1.5 text-xs text-text-primary bg-surface-muted border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {dueDate && (
            <button
              type="button"
              onClick={() => {
                setDueDate('');
                handleSaveFields({ due_at: null });
              }}
              className="px-2 py-1.5 text-xs text-text-muted hover:text-rose-500 rounded border border-border hover:border-rose-300"
              title="Очистить дату"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* 5. Editable Description */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Описание
          </label>
          {description !== (task.description_markdown ?? task.description ?? '') && (
            <button
              type="button"
              onClick={() => handleSaveFields({ description })}
              className="text-[11px] font-semibold text-primary hover:underline"
            >
              Сохранить описание
            </button>
          )}
        </div>
        <textarea
          rows={5}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => {
            if (description !== (task.description_markdown ?? task.description ?? '')) {
              handleSaveFields({ description });
            }
          }}
          placeholder="Добавьте подробное описание задачи..."
          className="w-full px-3 py-2 text-xs leading-relaxed text-text-primary bg-surface-muted hover:bg-surface focus:bg-surface border border-border focus:border-primary rounded-lg focus:outline-none focus:ring-1 focus:ring-primary resize-y"
        />
      </div>

      {/* 6. Subtasks Checklist */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Подзадачи ({localSubtasks.filter((s) => s.completed).length}/{localSubtasks.length})
          </label>
        </div>

        <div className="space-y-1.5 mb-2">
          {localSubtasks.map((sub) => (
            <div
              key={sub.id}
              className="flex items-center justify-between gap-2 p-1.5 rounded-lg bg-surface-muted border border-border text-xs"
            >
              <label className="flex items-center gap-2 flex-1 cursor-pointer min-w-0">
                <input
                  type="checkbox"
                  checked={sub.completed}
                  onChange={() => handleToggleSubtask(sub.id)}
                  className="rounded border-border text-primary focus:ring-primary/20 cursor-pointer"
                />
                <span className={cn('truncate', sub.completed && 'line-through text-text-muted')}>
                  {sub.title}
                </span>
              </label>
              <button
                type="button"
                onClick={() => handleDeleteSubtask(sub.id)}
                className="text-text-muted hover:text-rose-500 p-1"
                title="Удалить подзадачу"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <form onSubmit={handleAddSubtask} className="flex items-center gap-2">
          <input
            type="text"
            value={newSubtaskTitle}
            onChange={(e) => setNewSubtaskTitle(e.target.value)}
            placeholder="+ Добавить подзадачу..."
            className="flex-1 px-2.5 py-1 text-xs bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            type="submit"
            disabled={!newSubtaskTitle.trim()}
            className="px-2.5 py-1 text-xs font-semibold bg-primary text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
          >
            Добавить
          </button>
        </form>
      </div>

      {/* 7. Attachments & Files */}
      <TaskAttachmentsSection taskId={task.id} />

      {/* 8. Footer Actions */}
      <div className="pt-4 border-t border-border flex items-center justify-between">
        <button
          type="button"
          onClick={handleDelete}
          className="px-3 py-1.5 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-lg transition-colors flex items-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
          <span>Удалить задачу</span>
        </button>

        <button
          type="button"
          onClick={() => {
            closeTaskDetail();
            closeRightPanel();
          }}
          className="px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface-muted hover:bg-surface border border-border rounded-lg transition-colors"
        >
          Закрыть
        </button>
      </div>
    </article>
  );
}

export default TaskDetailPanel;


