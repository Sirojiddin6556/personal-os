'use client';

import React, { useState } from 'react';
import { useDailyAgenda } from '@/hooks/usePlanner';
import { useUpdateTask } from '@/hooks/useTasks';
import { HabitsWidget } from '@/components/domain/planner/HabitsWidget';
import { RemindersWidget } from '@/components/domain/planner/RemindersWidget';
import { DailyJournalWidget } from '@/components/domain/planner/DailyJournalWidget';
import { HourlyAgendaGrid } from '@/components/domain/planner/HourlyAgendaGrid';
import { FocusPomodoro } from '@/components/domain/planner/FocusPomodoro';
import { Task, TaskStatus } from '@/types/domain';

export default function PlannerPage() {
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split('T')[0]);
  const { data: agenda, isLoading, refetch } = useDailyAgenda(selectedDate);
  const updateTaskMutation = useUpdateTask();

  const handleDateShift = (days: number) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + days);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const handleSetToday = () => {
    setSelectedDate(new Date().toISOString().split('T')[0]);
  };

  const formattedDateHeader = new Date(selectedDate + 'T00:00:00').toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  const isToday = selectedDate === new Date().toISOString().split('T')[0];

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      {/* 1. Header & Date Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface border border-border rounded-2xl p-5 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">📓</span>
            <h1 className="text-xl font-bold text-text-primary capitalize">
              Ежедневник
            </h1>
            {isToday && (
              <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-primary/10 text-primary">
                Сегодня
              </span>
            )}
          </div>
          <p className="text-xs text-text-muted mt-1 capitalize">
            {formattedDateHeader}
          </p>
        </div>

        {/* Date Navigator */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleDateShift(-1)}
            className="p-2 rounded-xl bg-surface-muted hover:bg-surface-elevated text-text-secondary transition-colors"
            title="Предыдущий день"
          >
            ←
          </button>
          <button
            onClick={handleSetToday}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-colors ${
              isToday
                ? 'bg-primary text-white shadow-xs'
                : 'bg-surface-muted hover:bg-surface-elevated text-text-primary'
            }`}
          >
            Сегодня
          </button>
          <button
            onClick={() => handleDateShift(1)}
            className="p-2 rounded-xl bg-surface-muted hover:bg-surface-elevated text-text-secondary transition-colors"
            title="Следующий день"
          >
            →
          </button>

          <input
            type="date"
            value={selectedDate}
            onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
            className="px-3 py-1.5 text-xs font-medium bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-hidden"
          />

          <button
            onClick={() => refetch()}
            className="p-2 rounded-xl bg-surface-muted hover:bg-surface-elevated text-text-muted hover:text-text-primary transition-colors"
            title="Обновить"
          >
            ↻
          </button>
        </div>
      </div>

      {/* 2. Overview Stats Banner */}
      {agenda?.stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-xs text-text-muted block">Дела & Задачи</span>
            <span className="text-lg font-black text-text-primary mt-1 block">
              {agenda.stats.completed_tasks} / {agenda.stats.total_tasks}
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-xs text-text-muted block">Привычки</span>
            <span className="text-lg font-black text-emerald-600 dark:text-emerald-400 mt-1 block">
              {agenda.stats.completed_habits} / {agenda.stats.total_habits}
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-xs text-text-muted block">Тайм-блоки</span>
            <span className="text-lg font-black text-blue-600 dark:text-blue-400 mt-1 block">
              {agenda.stats.total_timeblocks} запланировано
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-xs text-text-muted block">Напоминания</span>
            <span className="text-lg font-black text-amber-600 dark:text-amber-400 mt-1 block">
              {agenda.reminders.length} активных
            </span>
          </div>
        </div>
      )}

      {/* 3. Main Two-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Timeline & Focus Timer (7 cols on lg) */}
        <div className="lg:col-span-7 space-y-6">
          <FocusPomodoro />

          <HourlyAgendaGrid
            timeBlocks={agenda?.time_blocks || []}
            tasks={agenda?.tasks || []}
            targetDate={selectedDate}
          />

          {/* Today's Tasks Checklist */}
          <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">📋</span>
                <h3 className="text-sm font-bold text-text-primary">Список дел на день</h3>
              </div>
              <a href="/tasks" className="text-xs text-primary font-semibold hover:underline">
                Все задачи →
              </a>
            </div>

            <div className="space-y-2">
              {agenda?.tasks.length === 0 ? (
                <p className="text-center py-4 text-xs text-text-muted">
                  На этот день нет запланированных задач.
                </p>
              ) : (
                agenda?.tasks.map((task: Task) => (
                  <div
                    key={task.id}
                    className={`flex items-center justify-between p-3 rounded-xl border transition-all ${
                      task.status === 'done'
                        ? 'bg-surface-muted/60 border-border text-text-muted line-through'
                        : 'bg-surface border-border hover:border-border-subtle text-text-primary'
                    }`}
                  >
                    <label className="flex items-center gap-3 cursor-pointer flex-1 select-none">
                      <input
                        type="checkbox"
                        checked={task.status === 'done'}
                        onChange={() =>
                          updateTaskMutation.mutate({
                            id: task.id,
                            version: task.version || 1,
                            status: task.status === 'done' ? TaskStatus.TODO : TaskStatus.DONE,
                          })
                        }
                        className="w-4 h-4 rounded-sm text-primary border-border focus:ring-primary cursor-pointer"
                      />
                      <span className="text-xs font-medium">{task.title}</span>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-surface-muted text-text-muted">
                        {task.priority}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Habits, Reminders & Journal (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-6">
          <RemindersWidget
            reminders={agenda?.reminders || []}
            targetDate={selectedDate}
          />

          <HabitsWidget
            habits={agenda?.habits || []}
            targetDate={selectedDate}
          />

          <DailyJournalWidget
            journal={agenda?.journal || null}
            targetDate={selectedDate}
          />
        </div>
      </div>
    </div>
  );
}
