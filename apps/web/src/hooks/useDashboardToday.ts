'use client';

import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { useTasks } from '@/hooks/useTasks';
import { useAccounts } from '@/hooks/useFinance';
import { useHabits, useToggleHabit } from '@/hooks/usePlanner';
import { Task, TaskStatus, CalendarEvent, BudgetSummary } from '@/types/domain';
import { MorningBrief } from '@/types/ai';

export interface HabitSummaryItem {
  id: string;
  title: string;
  target_count: number;
  current_streak: number;
  best_streak: number;
  completed_today: boolean;
}

export interface FreeTimeWindow {
  start: string;
  end: string;
  duration_minutes: number;
}

export interface ApiDashboardToday {
  events?: Array<{
    id: string;
    title: string;
    starts_at?: string;
    ends_at?: string;
    start_time?: string;
    end_time?: string;
    is_all_day?: boolean;
    location?: string;
    status?: string;
    is_external?: boolean;
    color?: string;
  }>;
  top_tasks?: Task[];
  overdue_tasks?: Task[];
  overdue_count?: number;
  free_windows?: FreeTimeWindow[];
  budget_summary?: {
    total_balance_minor: number;
    today_spent_minor?: number;
    monthly_spent_minor?: number;
    monthly_limit_minor?: number;
    currency: string;
    active_accounts_count: number;
  };
  habits?: HabitSummaryItem[];
  stats?: {
    total_tasks: number;
    completed_tasks: number;
    overdue_count: number;
    events_count: number;
    free_hours: number;
  };
}

export function useDashboardToday() {
  const queryClient = useQueryClient();
  const { tasks, isLoading: tasksLoading } = useTasks();
  const { accounts, isLoading: accountsLoading } = useAccounts();
  const { data: plannerHabits, isLoading: habitsLoading } = useHabits();
  const toggleHabitMutation = useToggleHabit();

  const [dismissedBrief, setDismissedBrief] = useState(false);

  // 1. Fetch dashboard overview from backend API
  const { data: apiDashboard, isLoading: dashboardLoading, refetch } = useQuery<ApiDashboardToday>({
    queryKey: queryKeys.dashboard.today(),
    queryFn: async () => {
      try {
        return await apiRequest<ApiDashboardToday>('GET', '/dashboard/today');
      } catch {
        return { events: [], top_tasks: [], overdue_tasks: [], overdue_count: 0 };
      }
    },
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  // 2. Compute dynamic top tasks and overdue tasks
  const topTasks = useMemo(() => {
    if (tasks && tasks.length > 0) {
      return tasks.filter((t) => t.status !== TaskStatus.DONE && t.status !== TaskStatus.CANCELLED).slice(0, 3);
    }
    return apiDashboard?.top_tasks || [];
  }, [tasks, apiDashboard]);

  const overdueTasks = useMemo(() => {
    if (tasks && tasks.length > 0) {
      const now = new Date();
      return tasks.filter(
        (t) =>
          t.status !== TaskStatus.DONE &&
          t.status !== TaskStatus.CANCELLED &&
          t.due_at &&
          new Date(t.due_at).getTime() < now.getTime()
      );
    }
    return apiDashboard?.overdue_tasks || [];
  }, [tasks, apiDashboard]);

  // 3. Dynamic agenda events
  const agenda: CalendarEvent[] = useMemo(() => {
    if (apiDashboard?.events && apiDashboard.events.length > 0) {
      return apiDashboard.events.map((e) => {
        const startTime = e.starts_at || e.start_time || new Date().toISOString();
        const endTime = e.ends_at || e.end_time || new Date().toISOString();
        const startFormatted = startTime.length >= 16 ? startTime.slice(11, 16) : '09:00';
        const endFormatted = endTime.length >= 16 ? endTime.slice(11, 16) : '10:00';

        return {
          id: e.id,
          title: e.title,
          start_time: startTime,
          end_time: endTime,
          start: e.is_all_day ? 'Весь день' : startFormatted,
          end: e.is_all_day ? '' : endFormatted,
          is_external: !!e.is_external || !!e.status,
          color: e.color || '#0ea5e9',
        };
      });
    }
    return [];
  }, [apiDashboard]);

  // 4. Dynamic budget summary
  const budgetSummary: BudgetSummary = useMemo(() => {
    const totalMinor =
      accounts.length > 0
        ? accounts.reduce((sum, acc) => sum + (acc.balance_minor || 0), 0)
        : apiDashboard?.budget_summary?.total_balance_minor || 0;

    const monthlySpentMinor = apiDashboard?.budget_summary?.monthly_spent_minor || 0;
    const monthlyLimitMinor = apiDashboard?.budget_summary?.monthly_limit_minor || 1500000000;
    const currency = apiDashboard?.budget_summary?.currency || 'UZS';

    const spent = Math.round(monthlySpentMinor / 100);
    const limit = Math.round(monthlyLimitMinor / 100);
    const pct = limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0;
    const remaining = Math.max(0, limit - spent);

    return {
      daily_spent_minor: apiDashboard?.budget_summary?.today_spent_minor || 0,
      monthly_spent_minor: monthlySpentMinor,
      monthly_limit_minor: monthlyLimitMinor,
      spent,
      limit,
      currency,
      percentage: pct,
      remaining,
      category: 'Все категории',
    };
  }, [accounts, apiDashboard]);

  // 5. Habits summary combining Planner domain
  const habits: HabitSummaryItem[] = useMemo(() => {
    if (plannerHabits && plannerHabits.length > 0) {
      return plannerHabits.map((h) => ({
        id: h.id,
        title: h.title,
        target_count: h.target_count,
        current_streak: h.current_streak,
        best_streak: h.best_streak,
        completed_today: h.is_completed_today,
      }));
    }
    return apiDashboard?.habits || [];
  }, [plannerHabits, apiDashboard]);

  const handleToggleHabit = async (habitId: string) => {
    await toggleHabitMutation.mutateAsync({ habitId });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
  };

  // 6. Free windows
  const freeWindows = apiDashboard?.free_windows || [];

  // 7. Morning Brief
  const brief: MorningBrief | null = useMemo(() => {
    if (dismissedBrief) return null;
    const pendingTasks = topTasks.length;
    const eventsCount = agenda.length;
    if (pendingTasks === 0 && eventsCount === 0) return null;

    return {
      id: 'brief-today',
      date: new Date().toISOString().split('T')[0],
      stats: {
        events_count: eventsCount,
        tasks_count: pendingTasks,
        free_hours: apiDashboard?.stats?.free_hours ?? 3.5,
        critical_tasks_count: topTasks.filter((t) => t.priority === 'critical' || t.priority === 'high' || t.priority === 'urgent').length,
      },
      proposed_schedule: topTasks.map((t, idx) => ({
        id: `sched-${t.id || idx}`,
        time: idx === 0 ? '09:30 — 11:00' : idx === 1 ? '11:30 — 12:30' : '14:00 — 15:30',
        title: `Фокус: ${t.title}`,
        type: 'task',
      })),
      ai_comment:
        pendingTasks > 0
          ? `Сфокусируйтесь на приоритетной задаче «${topTasks[0]?.title}» в первую очередь.`
          : 'Все основные задачи на сегодня закрыты! Отличный темп.',
    };
  }, [dismissedBrief, topTasks, agenda, apiDashboard]);

  const totalTasksCount = tasks ? tasks.length : (apiDashboard?.stats?.total_tasks || 0);
  const completedTasksCount = tasks
    ? tasks.filter((t) => t.status === TaskStatus.DONE).length
    : (apiDashboard?.stats?.completed_tasks || 0);

  return {
    brief,
    dismissBrief: () => setDismissedBrief(true),
    topTasks,
    overdueTasks,
    overdueCount: overdueTasks.length || apiDashboard?.overdue_count || 0,
    agenda,
    budgetSummary,
    habits,
    freeWindows,
    handleToggleHabit,
    isLoading: tasksLoading || accountsLoading || dashboardLoading || habitsLoading,
    refetch,
    stats: {
      totalTasks: totalTasksCount,
      completedTasks: completedTasksCount,
      overdueCount: overdueTasks.length,
      eventsCount: agenda.length,
      freeHours: apiDashboard?.stats?.free_hours ?? 4.0,
    },
  };
}

