'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTasks } from '@/hooks/useTasks';
import { useProjects } from '@/hooks/useGitHub';
import { useUIStore } from '@/stores/ui-store';
import { KanbanBoard } from '@/components/domain/tasks/KanbanBoard';
import { TaskCard } from '@/components/domain/tasks/TaskCard';
import { TaskPriority, TaskStatus } from '@/types/domain';
import { cn } from '@/lib/utils';

export default function TasksPage() {
  const searchParams = useSearchParams();
  const urlProject = searchParams?.get('project') || 'all';

  const [view, setView] = useState<'kanban' | 'list'>('kanban');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [projectFilter, setProjectFilter] = useState<string>(urlProject);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: dbProjects = [] } = useProjects();

  useEffect(() => {
    const p = searchParams?.get('project');
    if (p) {
      setProjectFilter(p);
    }
  }, [searchParams]);

  const { tasks, moveTask, completeTask, deleteTask } = useTasks({
    status: statusFilter,
    priority: priorityFilter,
    project: projectFilter,
    search: searchQuery,
  });

  const { openQuickAdd, openTaskDetail } = useUIStore();

  const handleEdit = (id: string) => {
    openTaskDetail(id);
  };

  const handleMove = (taskId: string, targetStatus: TaskStatus, newIndex?: number) => {
    moveTask(taskId, targetStatus, newIndex);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden p-4 sm:p-6 space-y-4">
      {/* 1. Header Toolbar: Title, ViewSwitcher, Quick Add Button */}
      <div className="flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">
            Управление задачами
          </h1>
          <p className="text-xs text-text-secondary">
            Единое доменное ядро: статус задачи синхронизирован между списком и канбаном
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* ViewSwitcher: Kanban | List */}
          <div
            role="tablist"
            aria-label="Переключение вида задач"
            className="flex items-center p-1 bg-surface-muted rounded-xl border border-border shadow-2xs"
          >
            <button
              type="button"
              role="tab"
              aria-selected={view === 'kanban'}
              onClick={() => setView('kanban')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all',
                view === 'kanban'
                  ? 'bg-surface text-text-primary shadow-xs'
                  : 'text-text-muted hover:text-text-primary'
              )}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="5" height="18" rx="1" />
                <rect x="10" y="3" width="5" height="12" rx="1" />
                <rect x="17" y="3" width="5" height="15" rx="1" />
              </svg>
              <span>Канбан</span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={view === 'list'}
              onClick={() => setView('list')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all',
                view === 'list'
                  ? 'bg-surface text-text-primary shadow-xs'
                  : 'text-text-muted hover:text-text-primary'
              )}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" />
                <line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
              <span>Список</span>
            </button>
          </div>

          {/* Quick Add CTA */}
          <button
            type="button"
            onClick={() => openQuickAdd('task')}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-primary text-white text-xs font-bold hover:bg-primary-600 active:scale-95 transition-all shadow-xs"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Новая задача</span>
          </button>
        </div>
      </div>

      {/* 2. FilterBar: status, priority, project, search */}
      <div className="flex flex-wrap items-center gap-2.5 p-2.5 bg-surface border border-border rounded-xl shadow-2xs shrink-0">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <svg className="w-3.5 h-3.5 absolute left-3 top-2.5 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Фильтр по названию..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Priority Filter */}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          aria-label="Фильтр по приоритету"
          className="px-2.5 py-1.5 text-xs bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="all">Все приоритеты</option>
          <option value="critical">🔴 Критический</option>
          <option value="high">🟠 Высокий</option>
          <option value="medium">🔵 Средний</option>
          <option value="low">⚪ Низкий</option>
        </select>

        {/* Project Filter */}
        <select
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          aria-label="Фильтр по проекту"
          className="px-2.5 py-1.5 text-xs bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary max-w-[200px] truncate"
        >
          <option value="all">Все проекты ({dbProjects.length})</option>
          {dbProjects.map((p) => (
            <option key={p.id} value={p.id}>
              📁 {p.name}
            </option>
          ))}
        </select>

        {/* Status Filter (especially useful for List view) */}
        {view === 'list' && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Фильтр по статусу"
            className="px-2.5 py-1.5 text-xs bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">Все статусы</option>
            <option value="inbox">Входящие</option>
            <option value="todo">К выполнению</option>
            <option value="scheduled">Запланировано</option>
            <option value="in_progress">В работе</option>
            <option value="waiting">Ожидание</option>
            <option value="done">Завершено</option>
          </select>
        )}

        {/* Reset filters button */}
        {(statusFilter !== 'all' || priorityFilter !== 'all' || projectFilter !== 'all' || searchQuery) && (
          <button
            type="button"
            onClick={() => {
              setStatusFilter('all');
              setPriorityFilter('all');
              setProjectFilter('all');
              setSearchQuery('');
            }}
            className="text-xs text-text-muted hover:text-text-primary px-2 py-1 underline"
          >
            Сбросить
          </button>
        )}
      </div>

      {/* 3. View Area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {view === 'kanban' ? (
          <KanbanBoard
            tasks={tasks}
            onMoveTask={handleMove}
            onCompleteTask={completeTask}
            onEditTask={handleEdit}
            onDeleteTask={deleteTask}
          />
        ) : (
          /* List View with Infinite Scroll Pattern */
          <div className="h-[calc(100vh-200px)] overflow-y-auto space-y-3 pr-2">
            <div className="text-xs text-text-muted mb-2 font-medium">
              Отображается {tasks.length} задач
            </div>

            {tasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 border border-dashed border-border rounded-2xl text-center">
                <p className="text-sm font-semibold text-text-primary">Задач не найдено</p>
                <p className="text-xs text-text-muted mt-1">Попробуйте изменить параметры фильтрации</p>
              </div>
            ) : (
              tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onComplete={completeTask}
                  onEdit={handleEdit}
                  onDelete={deleteTask}
                />
              ))
            )}

            {/* Infinite Query Loading indicator mock */}
            <div className="py-4 text-center text-xs text-text-muted">
              ✓ Все доступные задачи загружены
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
