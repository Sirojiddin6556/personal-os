'use client';

import React from 'react';
import { useDashboardToday } from '@/hooks/useDashboardToday';
import { useUIStore } from '@/stores/ui-store';
import { MorningBriefCard } from '../notifications/MorningBriefCard';
import { TaskCard } from '../tasks/TaskCard';
import { Task } from '@/types/domain';
import { formatCurrency } from '@/lib/utils';
import { cn } from '@/lib/utils';

export function TodayDashboard() {
  const {
    brief,
    dismissBrief,
    topTasks,
    overdueTasks,
    agenda,
    budgetSummary,
    stats,
  } = useDashboardToday();

  const { openQuickAdd, openTaskDetail } = useUIStore();

  const handleTaskComplete = (id: string) => {
    console.log('Toggle complete task:', id);
  };

  const handleTaskEdit = (id: string) => {
    openTaskDetail(id);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      {/* 1. Overdue Alert Banner (if any overdue tasks) */}
      {overdueTasks.length > 0 && (
        <div
          role="alert"
          className="flex items-center justify-between p-3.5 sm:p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 shadow-xs"
        >
          <div className="flex items-center gap-3">
            <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-rose-600 text-white font-bold text-sm shrink-0">
              !
            </span>
            <div>
              <p className="text-sm font-bold text-rose-900 dark:text-rose-200">
                Внимание: {overdueTasks.length} просроченная задача требует решения
              </p>
              <p className="text-xs text-rose-700 dark:text-rose-400">
                Задачи с истекшим дедлайном блокируют запланированный график дня.
              </p>
            </div>
          </div>
          <a
            href="/tasks?status=todo"
            className="px-3 py-1.5 text-xs font-bold text-rose-700 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/60 rounded-lg transition-colors shrink-0"
          >
            Разобрать →
          </a>
        </div>
      )}

      {/* 2. Morning Brief Card (Full Width) */}
      {brief && (
        <MorningBriefCard
          brief={brief}
          onAccept={() => {
            alert('План на день принят! Тайм-блоки добавлены в календарь.');
            dismissBrief();
          }}
          onPartialAccept={(ids) => {
            alert(`Принято ${ids.length} блока из плана.`);
            dismissBrief();
          }}
          onDismiss={dismissBrief}
        />
      )}

      {/* 3. Main Grid: Top 3 Tasks & Today's Calendar Strip */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Top 3 Tasks Section (2 columns on lg) */}
        <section
          aria-labelledby="top-tasks-heading"
          className="lg:col-span-2 bg-surface border border-border rounded-2xl p-5 shadow-xs flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h3 id="top-tasks-heading" className="text-base font-bold text-text-primary">
                  Топ-3 задачи дня
                </h3>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-text-secondary">
                  {stats.completedTasks}/{stats.totalTasks} выполнено
                </span>
              </div>
              <a
                href="/tasks"
                className="text-xs font-semibold text-primary hover:underline"
              >
                Все задачи →
              </a>
            </div>

            {/* Task list */}
            <div className="space-y-3">
              {topTasks.slice(0, 3).map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onComplete={handleTaskComplete}
                  onEdit={handleTaskEdit}
                />
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between">
            <span className="text-xs text-text-muted">
              Сфокусируйтесь на приоритетах P0/P1
            </span>
            <button
              onClick={() => openQuickAdd('task')}
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
            >
              <span>+ Новая задача</span>
            </button>
          </div>
        </section>

        {/* Calendar Strip / Today Timeline (2 columns on lg) */}
        <section
          aria-labelledby="agenda-heading"
          className="lg:col-span-2 bg-surface border border-border rounded-2xl p-5 shadow-xs flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h3 id="agenda-heading" className="text-base font-bold text-text-primary">
                  Расписание и встречи
                </h3>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300">
                  {agenda.length} события
                </span>
              </div>
              <a
                href="/calendar"
                className="text-xs font-semibold text-primary hover:underline"
              >
                В календарь →
              </a>
            </div>

            {/* Timeline items */}
            <div className="space-y-2.5">
              {agenda.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-surface-muted/60 hover:bg-surface-muted border border-border transition-colors duration-fast"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold font-mono text-primary px-2 py-1 bg-primary/10 rounded-md">
                      {item.start} — {item.end}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-text-primary">{item.title}</p>
                      {item.is_external && (
                        <span className="text-[10px] text-text-muted">
                          Синхронизировано с Google Calendar
                        </span>
                      )}
                    </div>
                  </div>

                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: item.color || '#0ea5e9' }}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between text-xs text-text-muted">
            <span>Свободное окно: 12:30 — 14:00 (Обед и отдых)</span>
            <button
              onClick={() => openQuickAdd('event')}
              className="text-primary font-semibold hover:underline"
            >
              + Встреча
            </button>
          </div>
        </section>
      </div>

      {/* 4. Row 3: Budget Summary Bar & Habits Quick Check */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Budget Summary Bar (2 columns on lg) */}
        <section
          aria-labelledby="budget-summary-heading"
          className="lg:col-span-2 bg-surface border border-border rounded-2xl p-5 shadow-xs"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 id="budget-summary-heading" className="text-base font-bold text-text-primary">
              Бюджет на текущий месяц
            </h3>
            <a href="/finance" className="text-xs font-semibold text-primary hover:underline">
              Финансы →
            </a>
          </div>

          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="font-semibold text-text-secondary">
              Израсходовано {budgetSummary.percentage}%
            </span>
            <span className="font-mono text-text-primary font-bold">
              {budgetSummary.spent.toLocaleString('ru-RU')} / {budgetSummary.limit.toLocaleString('ru-RU')} ₽
            </span>
          </div>

          {/* Progress track */}
          <div className="w-full h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={budgetSummary.percentage}
              aria-valuemin={0}
              aria-valuemax={100}
              className={cn(
                'h-full rounded-full transition-all duration-300',
                budgetSummary.percentage > 90
                  ? 'bg-rose-500'
                  : budgetSummary.percentage > 70
                  ? 'bg-amber-500'
                  : 'bg-emerald-500'
              )}
              style={{ width: `${Math.min(budgetSummary.percentage, 100)}%` }}
            />
          </div>

          <div className="flex items-center justify-between mt-2 text-xs">
            <span className="text-text-muted">
              Остаток лимита: <strong className="text-emerald-600 font-mono">{budgetSummary.remaining.toLocaleString('ru-RU')} ₽</strong>
            </span>
            <span className="text-[11px] text-text-muted">Лимит обновляется 1-го числа</span>
          </div>
        </section>

        {/* Habits & Focus Streak (2 columns on lg) */}
        <section
          aria-labelledby="habits-summary-heading"
          className="lg:col-span-2 bg-surface border border-border rounded-2xl p-5 shadow-xs flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 id="habits-summary-heading" className="text-base font-bold text-text-primary">
                Привычки и продуктивность
              </h3>
              <span className="text-xs font-semibold text-purple-600 dark:text-purple-400">
                🔥 Стрик: 5 дней
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="p-2.5 rounded-xl bg-surface-muted border border-border flex items-center justify-between">
                <span className="font-medium text-text-primary">🏃 Утренняя зарядка</span>
                <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-bold">
                  ✓ Сделано
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-surface-muted border border-border flex items-center justify-between">
                <span className="font-medium text-text-primary">📚 Чтение 30 мин</span>
                <button className="px-2 py-0.5 rounded bg-surface border border-border text-text-secondary hover:text-primary font-medium">
                  Отметить
                </button>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-2 text-[11px] text-text-muted flex justify-between">
            <span>Фокусное время сегодня: 2ч 40м</span>
            <span>Цель: 4ч 00м</span>
          </div>
        </section>
      </div>
    </div>
  );
}

export default TodayDashboard;
