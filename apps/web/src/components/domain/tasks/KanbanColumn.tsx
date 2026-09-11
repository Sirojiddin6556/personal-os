'use client';

import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Task, TaskStatus } from '@/types/domain';
import { TaskCard } from './TaskCard';
import { cn } from '@/lib/utils';

export interface KanbanColumnProps {
  id: TaskStatus;
  title: string;
  dotColor?: string;
  tasks: Task[];
  onAddTask?: (status: TaskStatus) => void;
  onCompleteTask: (id: string) => void;
  onEditTask: (id: string) => void;
}

export function KanbanColumn({
  id,
  title,
  dotColor = '#6366f1',
  tasks,
  onAddTask,
  onCompleteTask,
  onEditTask,
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: {
      type: 'column',
      columnId: id,
    },
  });

  const taskIds = tasks.map((t) => t.id);

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'flex flex-col w-[310px] min-w-[310px] bg-slate-50/70 dark:bg-slate-900/60 border border-border rounded-xl p-3 max-h-full shrink-0 transition-colors duration-fast',
        isOver && 'border-primary/60 bg-primary/5 ring-1 ring-primary/30'
      )}
    >
      {/* Column Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          {/* Status Indicator Dot */}
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ backgroundColor: dotColor }}
          />
          <h3 className="text-sm font-bold text-text-primary tracking-tight">{title}</h3>
          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-surface text-text-secondary border border-border shadow-2xs">
            {tasks.length}
          </span>
        </div>

        {/* Add button */}
        {onAddTask && (
          <button
            type="button"
            onClick={() => onAddTask(id)}
            aria-label={`Добавить задачу в ${title}`}
            className="p-1 text-text-muted hover:text-text-primary rounded hover:bg-surface transition-colors"
            title="Добавить задачу"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        )}
      </div>

      {/* Sortable Droppable Cards Container */}
      <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
        <div className="flex flex-col gap-2.5 overflow-y-auto pr-1 flex-1 min-h-[160px]">
          {tasks.length === 0 ? (
            <div
              className={cn(
                'flex items-center justify-center border-2 border-dashed border-border/80 rounded-xl h-24 text-xs font-medium text-text-muted transition-colors',
                isOver && 'border-primary/60 bg-primary/5 text-primary'
              )}
            >
              {isOver ? 'Отпустите для переноса' : 'Нет задач'}
            </div>
          ) : (
            tasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onComplete={onCompleteTask}
                onEdit={onEditTask}
              />
            ))
          )}
        </div>
      </SortableContext>
    </div>
  );
}

export default KanbanColumn;
