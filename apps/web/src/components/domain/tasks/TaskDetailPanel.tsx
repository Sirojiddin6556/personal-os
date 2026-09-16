'use client';

import React from 'react';
import { useTask } from '@/hooks/useTasks';
import { useUIStore } from '@/stores/ui-store';

function formatDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function TaskDetailPanel({ taskId }: { taskId: string }) {
  const { task, isLoading, isError, error } = useTask(taskId);
  const description = task?.description_markdown ?? task?.description ?? '';

  if (isLoading) {
    return <div className="text-sm text-text-muted">Загрузка задачи…</div>;
  }

  if (isError || !task) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-danger">Не удалось загрузить задачу.</p>
        {error?.message && <p className="text-xs text-text-muted">{error.message}</p>}
      </div>
    );
  }

  return (
    <article className="space-y-5" data-testid="task-detail-panel">
      <div>
        <h4 className="text-base font-semibold text-text-primary break-words">{task.title}</h4>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-surface-muted px-2 py-1 text-text-secondary">{task.status}</span>
          <span className="rounded-full bg-surface-muted px-2 py-1 text-text-secondary">{task.priority}</span>
        </div>
      </div>

      <section>
        <h5 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Описание</h5>
        <div className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-text-secondary">
          {description || 'Описание отсутствует.'}
        </div>
      </section>

      <dl className="space-y-2 text-xs">
        {task.project?.name && (
          <div className="flex justify-between gap-3"><dt className="text-text-muted">Проект</dt><dd className="text-right text-text-secondary">{task.project.name}</dd></div>
        )}
        {(task.due_date ?? task.due_at) && (
          <div className="flex justify-between gap-3"><dt className="text-text-muted">Срок</dt><dd className="text-right text-text-secondary">{formatDate(task.due_date ?? task.due_at)}</dd></div>
        )}
        {task.scheduled_date && (
          <div className="flex justify-between gap-3"><dt className="text-text-muted">Запланировано</dt><dd className="text-right text-text-secondary">{task.scheduled_date}</dd></div>
        )}
      </dl>
    </article>
  );
}

export default TaskDetailPanel;
