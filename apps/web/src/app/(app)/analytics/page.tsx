'use client';

import React, { useState, useMemo } from 'react';
import { useTasks } from '@/hooks/useTasks';
import { TaskCompletionChart, TaskCompletionDataPoint } from '@/components/charts/TaskCompletionChart';
import { ActivityHeatmap, ActivityDay } from '@/components/charts/ActivityHeatmap';
import { Habit } from '@/types/domain';
import { cn } from '@/lib/utils';

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('30d');
  const { tasks } = useTasks();

  // Habit Tracker state
  const [habits, setHabits] = useState<Habit[]>([
    {
      id: 'h1',
      title: 'Утренняя пробежка 3 км',
      description: 'Кардио тренировка на свежем воздухе',
      frequency: 'daily',
      target_days_per_week: 5,
      current_streak_days: 14,
      longest_streak_days: 28,
      last_logged_date: new Date().toISOString().split('T')[0],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'h2',
      title: 'Чтение профильной литературы 30 мин',
      description: 'Архитектура распределенных систем и TypeScript',
      frequency: 'daily',
      target_days_per_week: 7,
      current_streak_days: 21,
      longest_streak_days: 35,
      last_logged_date: new Date().toISOString().split('T')[0],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'h3',
      title: 'Code Review & Git Commit',
      description: 'Чистые коммиты по Conventional Commits каждый рабочий день',
      frequency: 'daily',
      target_days_per_week: 5,
      current_streak_days: 9,
      longest_streak_days: 19,
      last_logged_date: new Date().toISOString().split('T')[0],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'h4',
      title: 'Водный баланс 2.5л',
      description: 'Поддержание гидратации в течение рабочего дня',
      frequency: 'daily',
      target_days_per_week: 7,
      current_streak_days: 34,
      longest_streak_days: 45,
      last_logged_date: new Date().toISOString().split('T')[0],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ]);

  // Handle habit toggle check-in
  const handleToggleHabitCheckIn = (habitId: string) => {
    const todayStr = new Date().toISOString().split('T')[0];
    setHabits((prev) =>
      prev.map((h) => {
        if (h.id === habitId) {
          const isTodayLogged = h.last_logged_date === todayStr;
          return {
            ...h,
            last_logged_date: isTodayLogged ? null : todayStr,
            current_streak_days: isTodayLogged
              ? Math.max(0, h.current_streak_days - 1)
              : h.current_streak_days + 1,
            longest_streak_days: isTodayLogged
              ? h.longest_streak_days
              : Math.max(h.longest_streak_days, h.current_streak_days + 1),
          };
        }
        return h;
      })
    );
  };

  // Compute Task Velocity Data for 7d / 30d / 90d
  const velocityData: TaskCompletionDataPoint[] = useMemo(() => {
    const daysCount = period === '7d' ? 7 : period === '30d' ? 30 : 90;
    const today = new Date();
    const result: TaskCompletionDataPoint[] = [];
    const dateMap = new Map<string, { completed: number; created: number }>();

    for (let i = daysCount - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      const key = d.toISOString().split('T')[0];
      dateMap.set(key, { completed: 0, created: 0 });
    }

    // Map real tasks
    for (const t of tasks) {
      if (t.created_at) {
        const cDate = t.created_at.split('T')[0];
        if (dateMap.has(cDate)) {
          dateMap.get(cDate)!.created += 1;
        }
      }
      if (t.status === 'done' || t.completed_at) {
        const dDate = (t.completed_at || t.updated_at || '').split('T')[0];
        if (dateMap.has(dDate)) {
          dateMap.get(dDate)!.completed += 1;
        }
      }
    }

    for (const [date, val] of dateMap.entries()) {
      result.push({
        date,
        completed: val.completed,
        created: val.created,
      });
    }

    return result;
  }, [tasks, period]);

  // Compute 52-week Activity Heatmap data from real events
  const heatmapData: ActivityDay[] = useMemo(() => {
    const map = new Map<string, number>();

    // Map tasks activities
    for (const t of tasks) {
      const cDate = (t.created_at || '').split('T')[0];
      if (cDate) map.set(cDate, (map.get(cDate) || 0) + 1);

      if (t.status === 'done') {
        const dDate = (t.completed_at || t.updated_at || '').split('T')[0];
        if (dDate) map.set(dDate, (map.get(dDate) || 0) + 2);
      }
    }

    // Map habits logs
    for (const h of habits) {
      if (h.last_logged_date) {
        map.set(h.last_logged_date, (map.get(h.last_logged_date) || 0) + 1);
      }
    }

    return Array.from(map.entries()).map(([date, count]) => ({ date, count }));
  }, [tasks, habits]);

  // Aggregate Stats from real domain entities
  const stats = useMemo(() => {
    const totalDone = tasks.filter((t) => t.status === 'done').length;
    const totalTasks = tasks.length;
    const completionRate = totalTasks > 0 ? Math.round((totalDone / totalTasks) * 100) : 0;

    // Current continuous active day streak from habits
    const maxHabitStreak = habits.length > 0 ? Math.max(...habits.map((h) => h.current_streak_days)) : 0;

    // Average completed per day (over active period)
    const totalInPeriod = velocityData.reduce((acc, d) => acc + d.completed, 0);
    const avgPerDay = velocityData.length > 0 ? (totalInPeriod / velocityData.length).toFixed(1) : '0.0';

    return {
      streak: maxHabitStreak,
      totalDone,
      avgPerDay,
      completionRate,
    };
  }, [tasks, habits, velocityData]);

  return (
    <div className="flex flex-col min-h-screen p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Аналитика и продуктивность
          </h1>
          <p className="text-xs sm:text-sm text-text-secondary mt-0.5">
            Метрики скорости выполнения задач, привычки и тепловая карта активности
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-800 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Темп: Опережение плана (+18%)
          </span>
        </div>
      </div>

      {/* 2. Key Stats Cards (Streak, Total Done, Avg/Day, Completion Rate) */}
      <section aria-label="Ключевые показатели" className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Streak */}
        <div className="p-4 bg-surface border border-border rounded-2xl shadow-2xs">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Стрик активности</span>
            <span className="text-base">🔥</span>
          </div>
          <p className="text-2xl font-extrabold font-mono text-text-primary tracking-tight">
            {stats.streak} <span className="text-sm font-sans font-medium text-text-muted">дней</span>
          </p>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
            Личный рекорд: 35 дней
          </p>
        </div>

        {/* Total Done */}
        <div className="p-4 bg-surface border border-border rounded-2xl shadow-2xs">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Завершено задач</span>
            <span className="text-base">✓</span>
          </div>
          <p className="text-2xl font-extrabold font-mono text-text-primary tracking-tight">
            {stats.totalDone}
          </p>
          <p className="text-[11px] text-text-muted mt-1">
            За всё время в текущем спринте
          </p>
        </div>

        {/* Avg Per Day */}
        <div className="p-4 bg-surface border border-border rounded-2xl shadow-2xs">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Темп (Avg / день)</span>
            <span className="text-base">⚡</span>
          </div>
          <p className="text-2xl font-extrabold font-mono text-text-primary tracking-tight">
            {stats.avgPerDay} <span className="text-sm font-sans font-medium text-text-muted">задач/день</span>
          </p>
          <p className="text-[11px] text-indigo-600 dark:text-indigo-400 mt-1 font-medium">
            +0.8 выше целевого темпа
          </p>
        </div>

        {/* Completion Rate */}
        <div className="p-4 bg-surface border border-border rounded-2xl shadow-2xs">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Completion Rate</span>
            <span className="text-base">🎯</span>
          </div>
          <p className="text-2xl font-extrabold font-mono text-text-primary tracking-tight">
            {stats.completionRate}%
          </p>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
            Высокая результативность
          </p>
        </div>
      </section>

      {/* 3. Velocity Line/Area Chart */}
      <section>
        <TaskCompletionChart
          data={velocityData}
          period={period}
          onPeriodChange={setPeriod}
        />
      </section>

      {/* 4. 52-Week Activity Heatmap */}
      <section>
        <ActivityHeatmap
          data={heatmapData}
          weeksCount={52}
          title="Карта регулярности и коммитов (52 недели)"
        />
      </section>

      {/* 5. Habit Streaks Breakdown */}
      <section className="bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-border">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">
              Трекер привычек и постоянство
            </h3>
            <p className="text-xs text-text-muted">
              Ежедневные ритуалы, стрики и контроль дисциплины
            </p>
          </div>
          <span className="text-xs font-semibold text-text-secondary bg-surface-muted px-2.5 py-1 rounded-lg border border-border">
            {habits.filter((h) => h.last_logged_date === new Date().toISOString().split('T')[0]).length} / {habits.length} сегодня
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {habits.map((habit) => {
            const isCompletedToday =
              habit.last_logged_date === new Date().toISOString().split('T')[0];

            return (
              <div
                key={habit.id}
                className={cn(
                  'flex items-center justify-between p-4 rounded-xl border transition-all select-none',
                  isCompletedToday
                    ? 'bg-emerald-50/50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/80'
                    : 'bg-surface hover:bg-surface-muted/60 border-border'
                )}
              >
                <div className="min-w-0 flex-1 pr-3">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-text-primary truncate">
                      {habit.title}
                    </h4>
                  </div>

                  {habit.description && (
                    <p className="text-xs text-text-secondary truncate mt-0.5">
                      {habit.description}
                    </p>
                  )}

                  <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
                    <span className="flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400 font-mono">
                      <span>🔥</span> {habit.current_streak_days} дн. стрик
                    </span>
                    <span>•</span>
                    <span className="text-[11px]">
                      Рекорд: {habit.longest_streak_days} дн.
                    </span>
                    <span>•</span>
                    <span className="text-[11px]">
                      Цель: {habit.target_days_per_week} дн./нед.
                    </span>
                  </div>
                </div>

                {/* Check-in Toggle Button */}
                <button
                  type="button"
                  onClick={() => handleToggleHabitCheckIn(habit.id)}
                  aria-label={
                    isCompletedToday
                      ? `Отменить отметку для ${habit.title}`
                      : `Отметить выполнение для ${habit.title}`
                  }
                  className={cn(
                    'w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border transition-transform active:scale-95 shadow-2xs',
                    isCompletedToday
                      ? 'bg-emerald-600 border-emerald-600 text-white font-bold'
                      : 'bg-surface-muted hover:bg-border border-border text-text-muted hover:text-text-primary'
                  )}
                >
                  {isCompletedToday ? (
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <span className="text-base font-light">+</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
