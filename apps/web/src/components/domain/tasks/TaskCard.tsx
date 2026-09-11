'use client';

import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Task } from '@/types/domain';
import { cn, formatDateShort } from '@/lib/utils';

export interface TaskCardProps {
  task: Task;
  onComplete: (id: string) => void;
  onEdit: (id: string) => void;
  isDragging?: boolean;
}

export function TaskCard({
  task,
  onComplete,
  onEdit,
  isDragging: isCustomDragging,
}: TaskCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const isDragging = isCustomDragging || isSortableDragging;

  // Overdue check
  const isOverdue =
    task.due_at &&
    task.status !== 'done' &&
    new Date(task.due_at).getTime() < Date.now();

  // Subtasks completion
  const subtasks = task.subtasks || [];
  const completedSubtasks = subtasks.filter((s) => s.completed).length;

  const isCompleted = task.status === 'done';

  const priorityStyles = {
    critical: 'bg-rose-100 text-rose-700 dark:bg-rose-950/80 dark:text-rose-300 border-rose-200 dark:border-rose-900',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-950/80 dark:text-orange-300 border-orange-200 dark:border-orange-900',
    medium: 'bg-sky-100 text-sky-700 dark:bg-sky-950/80 dark:text-sky-300 border-sky-200 dark:border-sky-900',
    low: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      role="article"
      aria-label={`Задача: ${task.title}`}
      className={cn(
        'group relative flex flex-col p-3 bg-surface hover:bg-surface border border-border hover:border-primary/40 rounded-xl shadow-xs hover:shadow-md transition-all duration-150 select-none text-left',
        isDragging && 'opacity-50 ring-2 ring-primary shadow-xl scale-[1.02]',
        isCompleted && 'opacity-65'
      )}
    >
      {/* Top row: Drag handle, Project tag, Priority badge */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {/* Drag Handle */}
          <button
            {...attributes}
            {...listeners}
            type="button"
            tabIndex={0}
            aria-label="Перетащить карточку"
            className="p-1 -ml-1 text-text-muted hover:text-text-primary cursor-grab active:cursor-grabbing rounded focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="9" cy="6" r="1.5" />
              <circle cx="15" cy="6" r="1.5" />
              <circle cx="9" cy="12" r="1.5" />
              <circle cx="15" cy="12" r="1.5" />
              <circle cx="9" cy="18" r="1.5" />
              <circle cx="15" cy="18" r="1.5" />
            </svg>
          </button>

          {/* Project Tag */}
          {task.project && (
            <span
              className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 truncate"
            >
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: task.project.color || '#6366f1' }}
              />
              <span className="truncate">#{task.project.name}</span>
            </span>
          )}
        </div>

        {/* Priority Badge */}
        <span
          className={cn(
            'inline-flex items-center text-[10px] font-bold px-1.5 py-0.5 rounded border uppercase shrink-0',
            priorityStyles[task.priority] || priorityStyles.medium
          )}
        >
          !{task.priority}
        </span>
      </div>

      {/* Middle row: Checkbox + Title */}
      <div className="flex items-start gap-2.5 mb-2">
        <input
          type="checkbox"
          checked={isCompleted}
          onChange={() => onComplete(task.id)}
          aria-label={isCompleted ? 'Отметить невыполненной' : 'Отметить выполненной'}
          className="mt-0.5 w-4 h-4 rounded border-border text-primary focus:ring-primary/20 cursor-pointer shrink-0 transition-colors"
        />
        <button
          type="button"
          onClick={() => onEdit(task.id)}
          className={cn(
            'text-sm font-medium text-text-primary leading-snug text-left group-hover:text-primary transition-colors focus:outline-none focus:underline',
            isCompleted && 'line-through text-text-muted'
          )}
        >
          {task.title}
        </button>
      </div>

      {/* Bottom row: Due Date + Subtasks */}
      <div className="flex items-center justify-between pt-2 border-t border-border-subtle text-xs text-text-secondary">
        {/* Due Date */}
        {task.due_at ? (
          <div
            className={cn(
              'inline-flex items-center gap-1 font-medium',
              isOverdue
                ? 'text-rose-600 dark:text-rose-400 font-bold'
                : 'text-text-muted'
            )}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>
              {isOverdue && '⚠️ '}
              {formatDateShort(task.due_at)}
            </span>
          </div>
        ) : (
          <span />
        )}

        {/* Subtask count */}
        {subtasks.length > 0 && (
          <div className="flex items-center gap-1 text-text-muted">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 11 12 14 22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
            <span>
              {completedSubtasks}/{subtasks.length}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default TaskCard;
