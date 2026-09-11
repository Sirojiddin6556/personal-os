'use client';

import { useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { Task, TimeBlock } from '@/types/domain';

export interface Habit {
  id: string;
  workspace_id: string;
  title: string;
  description?: string | null;
  frequency_type: 'daily' | 'weekdays' | 'weekends' | 'weekly';
  target_count: number;
  current_streak: number;
  best_streak: number;
  is_archived: boolean;
  is_completed_today: boolean;
  today_count: number;
  created_at: string;
  updated_at: string;
}

export interface HabitCreateInput {
  title: string;
  description?: string | null;
  frequency_type?: 'daily' | 'weekdays' | 'weekends' | 'weekly';
  target_count?: number;
}

export interface DailyJournal {
  id: string;
  workspace_id: string;
  entry_date: string;
  morning_intention?: string | null;
  gratitude?: string | null;
  notes?: string | null;
  evening_reflection?: string | null;
  mood?: string | null;
  productivity_rating?: number | null;
  created_at: string;
  updated_at: string;
}

export interface DailyJournalInput {
  entry_date: string;
  morning_intention?: string | null;
  gratitude?: string | null;
  notes?: string | null;
  evening_reflection?: string | null;
  mood?: string | null;
  productivity_rating?: number | null;
}

export interface PlannerReminder {
  id: string;
  workspace_id: string;
  title: string;
  remind_at: string;
  remind_type: 'task' | 'habit' | 'event' | 'custom';
  related_id?: string | null;
  is_dismissed: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlannerReminderCreateInput {
  title: string;
  remind_at: string;
  remind_type?: 'task' | 'habit' | 'event' | 'custom';
  related_id?: string | null;
}

export interface DailyAgenda {
  target_date: string;
  tasks: Task[];
  time_blocks: TimeBlock[];
  habits: Habit[];
  journal: DailyJournal | null;
  reminders: PlannerReminder[];
  stats: {
    total_tasks: number;
    completed_tasks: number;
    total_habits: number;
    completed_habits: number;
    total_timeblocks: number;
  };
}

export const plannerKeys = {
  all: ['planner'] as const,
  agenda: (date: string) => [...plannerKeys.all, 'agenda', date] as const,
  habits: (date?: string) => [...plannerKeys.all, 'habits', date || 'today'] as const,
  journal: (date: string) => [...plannerKeys.all, 'journal', date] as const,
  reminders: () => [...plannerKeys.all, 'reminders'] as const,
};

export function useDailyAgenda(targetDate?: string) {
  const dateStr = targetDate || new Date().toISOString().split('T')[0];
  return useQuery<DailyAgenda>({
    queryKey: plannerKeys.agenda(dateStr),
    queryFn: () =>
      apiRequest<DailyAgenda>('GET', '/planner/agenda', {
        params: { target_date: dateStr },
      }),
    refetchInterval: 30000,
  });
}

export function useHabits(targetDate?: string) {
  const dateStr = targetDate || new Date().toISOString().split('T')[0];
  return useQuery<Habit[]>({
    queryKey: plannerKeys.habits(dateStr),
    queryFn: () =>
      apiRequest<Habit[]>('GET', '/planner/habits', {
        params: { target_date: dateStr },
      }),
  });
}

export function useCreateHabit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: HabitCreateInput) =>
      apiRequest<Habit, HabitCreateInput>('POST', '/planner/habits', { body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

export function useToggleHabit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ habitId, date }: { habitId: string; date?: string }) =>
      apiRequest<Habit>('POST', `/planner/habits/${habitId}/toggle`, {
        params: date ? { target_date: date } : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

export function useDeleteHabit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (habitId: string) =>
      apiRequest('DELETE', `/planner/habits/${habitId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

export function useDailyJournal(dateStr: string) {
  return useQuery<DailyJournal | null>({
    queryKey: plannerKeys.journal(dateStr),
    queryFn: () =>
      apiRequest<DailyJournal | null>('GET', '/planner/journal', {
        params: { entry_date: dateStr },
      }),
  });
}

export function useSaveDailyJournal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DailyJournalInput) =>
      apiRequest<DailyJournal, DailyJournalInput>('PUT', '/planner/journal', { body: data }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.journal(vars.entry_date) });
      queryClient.invalidateQueries({ queryKey: plannerKeys.agenda(vars.entry_date) });
    },
  });
}

export function useReminders() {
  return useQuery<PlannerReminder[]>({
    queryKey: plannerKeys.reminders(),
    queryFn: () => apiRequest<PlannerReminder[]>('GET', '/planner/reminders'),
    refetchInterval: 15000,
  });
}

export function useCreateReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PlannerReminderCreateInput) =>
      apiRequest<PlannerReminder, PlannerReminderCreateInput>('POST', '/planner/reminders', { body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.reminders() });
      queryClient.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

export function useDismissReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: string) =>
      apiRequest('POST', `/planner/reminders/${reminderId}/dismiss`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plannerKeys.reminders() });
      queryClient.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

/**
 * Hook to manage browser push notifications and alarms for scheduled reminders.
 */
export function useNotificationReminders() {
  const { data: reminders = [] } = useReminders();
  const dismissMutation = useDismissReminder();

  const requestPermission = useCallback(async () => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      return await Notification.requestPermission();
    }
    return 'denied';
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    const interval = setInterval(() => {
      const now = new Date().getTime();
      reminders.forEach((r) => {
        if (r.is_dismissed) return;
        const remindTime = new Date(r.remind_at).getTime();
        // If due within the last 1 minute and not future
        if (now >= remindTime && now - remindTime < 60000) {
          try {
            new Notification('🔔 Напоминание — Personal OS', {
              body: r.title,
              icon: '/icon-192.png',
            });
            dismissMutation.mutate(r.id);
          } catch {
            // Ignore notification display failures
          }
        }
      });
    }, 10000);

    return () => clearInterval(interval);
  }, [reminders, dismissMutation]);

  return { requestPermission, hasPermission: typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted' };
}
