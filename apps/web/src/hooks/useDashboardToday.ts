'use client';

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { useTasks } from '@/hooks/useTasks';
import { useAccounts } from '@/hooks/useFinance';
import { Task, TaskStatus, CalendarEvent, BudgetSummary } from '@/types/domain';
import { MorningBrief } from '@/types/ai';

interface ApiDashboardToday {
  events?: Array<{
    id: string;
    title: string;
    start_time?: string;
    end_time?: string;
    start?: string;
    end?: string;
    is_external?: boolean;
    color?: string;
  }>;
  top_tasks?: Task[];
  overdue_count?: number;
  budget_summary?: {
    total_balance_minor: number;
    currency: string;
    active_accounts_count: number;
  };
}

export function useDashboardToday() {
  const { tasks, isLoading: tasksLoading } = useTasks();
  const { accounts, isLoading: accountsLoading } = useAccounts();

  const totalBalanceMinor = useMemo(() => {
    return accounts.reduce((sum, acc) => sum + (acc.balance_minor || 0), 0);
  }, [accounts]);

  const [dismissedBrief, setDismissedBrief] = useState(false);

  // 1. Fetch dashboard overview from backend API
  const { data: apiDashboard, isLoading: dashboardLoading } = useQuery<ApiDashboardToday>({
    queryKey: queryKeys.dashboard.today(),
    queryFn: async () => {
      try {
        return await apiRequest<ApiDashboardToday>('GET', '/dashboard/today');
      } catch {
        return { events: [], top_tasks: [], overdue_count: 0 };
      }
    },
    staleTime: 30 * 1000,
  });

  // 2. Compute dynamic top tasks and overdue tasks from actual domain tasks
  const topTasks = useMemo(() => {
    if (tasks && tasks.length > 0) {
      return tasks.filter((t) => t.status !== TaskStatus.DONE).slice(0, 3);
    }
    return apiDashboard?.top_tasks || [];
  }, [tasks, apiDashboard]);

  const overdueTasks = useMemo(() => {
    if (tasks && tasks.length > 0) {
      const now = new Date();
      return tasks.filter(
        (t) =>
          t.status !== TaskStatus.DONE &&
          t.due_at &&
          new Date(t.due_at).getTime() < now.getTime()
      );
    }
    return [];
  }, [tasks]);

  // 3. Compute dynamic agenda events
  const agenda: CalendarEvent[] = useMemo(() => {
    if (apiDashboard?.events && apiDashboard.events.length > 0) {
      return apiDashboard.events.map((e) => ({
        id: e.id,
        title: e.title,
        start_time: e.start_time || e.start || new Date().toISOString(),
        end_time: e.end_time || e.end || new Date().toISOString(),
        start: e.start || (e.start_time ? e.start_time.slice(11, 16) : '09:00'),
        end: e.end || (e.end_time ? e.end_time.slice(11, 16) : '10:00'),
        is_external: !!e.is_external,
        color: e.color || '#0ea5e9',
      }));
    }
    return [];
  }, [apiDashboard]);

  // 4. Compute dynamic budget summary from actual finance state
  const budgetSummary: BudgetSummary = useMemo(() => {
    const totalMinor = totalBalanceMinor || apiDashboard?.budget_summary?.total_balance_minor || 0;
    const limitMinor = 1500000000; // 15,000,000 UZS baseline monthly budget
    const spentMinor = Math.max(0, limitMinor - totalMinor);
    const pct = limitMinor > 0 ? Math.min(100, Math.round((spentMinor / limitMinor) * 100)) : 0;

    return {
      daily_spent_minor: 0,
      monthly_spent_minor: spentMinor,
      monthly_limit_minor: limitMinor,
      spent: Math.round(spentMinor / 100),
      limit: Math.round(limitMinor / 100),
      currency: 'UZS',
      percentage: pct,
      remaining: Math.max(0, Math.round((limitMinor - spentMinor) / 100)),
      category: 'Все категории',
    };
  }, [totalBalanceMinor, apiDashboard]);

  // 5. Morning Brief
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
        free_hours: 4.0,
        critical_tasks_count: topTasks.filter((t) => t.priority === 'critical' || t.priority === 'high').length,
      },
      proposed_schedule: topTasks.map((t, idx) => ({
        id: `sched-${t.id || idx}`,
        time: idx === 0 ? '09:30 — 11:00' : idx === 1 ? '11:30 — 12:30' : '14:00 — 15:30',
        title: `Фокус: ${t.title}`,
        type: 'task',
      })),
      ai_comment:
        pendingTasks > 0
          ? `Сфокусируйтесь на задаче «${topTasks[0]?.title}» до начала дневных встреч.`
          : 'Все запланированные задачи выполнены! Отличная продуктивность.',
    };
  }, [dismissedBrief, topTasks, agenda]);

  const totalTasksCount = tasks ? tasks.length : 0;
  const completedTasksCount = tasks ? tasks.filter((t) => t.status === TaskStatus.DONE).length : 0;

  return {
    brief,
    dismissBrief: () => setDismissedBrief(true),
    topTasks,
    overdueTasks,
    agenda,
    budgetSummary,
    isLoading: tasksLoading || dashboardLoading,
    stats: {
      totalTasks: totalTasksCount,
      completedTasks: completedTasksCount,
      overdueCount: overdueTasks.length,
      eventsCount: agenda.length,
      freeHours: 4.0,
    },
  };
}

