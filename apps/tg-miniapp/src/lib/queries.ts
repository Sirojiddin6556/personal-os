import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, newIdempotencyKey } from './api';
import { isoDate } from './format';
import type {
  Account,
  AIPlan,
  Category,
  CursorPage,
  DashboardToday,
  Habit,
  Journal,
  MorningBrief,
  Priority,
  Reminder,
  Task,
  Transaction,
} from './types';

export const keys = {
  today: ['today'] as const,
  brief: ['brief'] as const,
  tasks: ['tasks'] as const,
  accounts: ['accounts'] as const,
  categories: ['categories'] as const,
  transactions: ['transactions'] as const,
  habits: ['habits'] as const,
  reminders: ['reminders'] as const,
  journal: (d: string) => ['journal', d] as const,
};

// ------------------------------------------------------------------ reads
export const useToday = () =>
  useQuery({ queryKey: keys.today, queryFn: () => api<DashboardToday>('/dashboard/today') });

export const useBrief = () =>
  useQuery({
    queryKey: keys.brief,
    queryFn: () => api<MorningBrief>('/advisor/brief'),
    retry: false,
    staleTime: 30 * 60 * 1000,
  });

export const useTasks = () =>
  useQuery({
    queryKey: keys.tasks,
    queryFn: async () => (await api<CursorPage<Task>>('/tasks?limit=200')).items,
  });

export const useAccounts = () =>
  useQuery({ queryKey: keys.accounts, queryFn: () => api<Account[]>('/finance/accounts') });

export const useCategories = () =>
  useQuery({ queryKey: keys.categories, queryFn: () => api<Category[]>('/finance/categories') });

export const useTransactions = () =>
  useQuery({
    queryKey: keys.transactions,
    queryFn: () => api<Transaction[]>('/finance/transactions?limit=100'),
  });

export const useHabits = () =>
  useQuery({ queryKey: keys.habits, queryFn: () => api<Habit[]>('/planner/habits') });

export const useReminders = () =>
  useQuery({ queryKey: keys.reminders, queryFn: () => api<Reminder[]>('/planner/reminders') });

export const useJournal = (date: string) =>
  useQuery({
    queryKey: keys.journal(date),
    queryFn: () => api<Journal | null>(`/planner/journal?entry_date=${date}`),
  });

// ------------------------------------------------------------------ writes
function useInvalidate() {
  const qc = useQueryClient();
  return (...ks: ReadonlyArray<readonly unknown[]>) =>
    Promise.all(ks.map((k) => qc.invalidateQueries({ queryKey: k })));
}

export function useToggleTask() {
  const qc = useQueryClient();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (task: Task) => {
      if (task.status === 'done') {
        return api<Task>(`/tasks/${task.id}`, {
          method: 'PATCH',
          body: { status: 'todo' },
          headers: { 'If-Match': `"${task.version}"` },
        });
      }
      return api<Task>(`/tasks/${task.id}/complete`, { method: 'POST' });
    },
    // Optimistic flip so the checkbox reacts instantly.
    onMutate: async (task) => {
      await qc.cancelQueries({ queryKey: keys.tasks });
      const prev = qc.getQueryData<Task[]>(keys.tasks);
      qc.setQueryData<Task[]>(keys.tasks, (list) =>
        list?.map((t) => (t.id === task.id ? { ...t, status: task.status === 'done' ? 'todo' : 'done' } : t)),
      );
      return { prev };
    },
    onError: (_e, _t, ctx) => ctx?.prev && qc.setQueryData(keys.tasks, ctx.prev),
    onSettled: () => invalidate(keys.tasks, keys.today),
  });
}

export function useUpdateTask() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ task, patch }: { task: Task; patch: Partial<Pick<Task, 'priority' | 'due_at' | 'status'>> }) =>
      api<Task>(`/tasks/${task.id}`, {
        method: 'PATCH',
        body: patch,
        headers: { 'If-Match': `"${task.version}"` },
      }),
    onSettled: () => invalidate(keys.tasks, keys.today),
  });
}

export function useCreateTask() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { title: string; priority: Priority; due_at: string | null }) =>
      api<Task>('/tasks', {
        body: { ...body, status: body.due_at ? 'todo' : 'inbox' },
        headers: { 'Idempotency-Key': newIdempotencyKey() },
      }),
    onSuccess: () => invalidate(keys.tasks, keys.today),
  });
}

export function useCreateExpense() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: {
      account_id: string;
      amount_minor: number;
      currency: string;
      category_id?: string;
      category_name?: string;
      note: string;
    }) =>
      api<Transaction>('/finance/transactions', {
        body: { ...body, transaction_type: 'expense' },
        headers: { 'Idempotency-Key': newIdempotencyKey() },
      }),
    onSuccess: () => invalidate(keys.transactions, keys.accounts, keys.today),
  });
}

export function useCreateReminder() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { title: string; remind_at: string }) =>
      api<Reminder>('/planner/reminders', { body: { ...body, remind_type: 'custom' } }),
    onSuccess: () => invalidate(keys.reminders),
  });
}

export function useToggleHabit() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (habitId: string) =>
      api<Habit>(`/planner/habits/${habitId}/toggle?target_date=${isoDate()}`, { method: 'POST' }),
    onSettled: () => invalidate(keys.habits, keys.today),
  });
}

export function useSaveJournal() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { entry_date: string; evening_reflection: string }) =>
      api<Journal>('/planner/journal', { method: 'PUT', body }),
    onSuccess: (_d, v) => invalidate(keys.journal(v.entry_date)),
  });
}

export function useCreatePlan() {
  return useMutation({
    mutationFn: () =>
      api<AIPlan>('/ai/plans', {
        body: { request: 'Спланируй мой день: распредели главные задачи по свободным окнам.' },
      }),
  });
}

export function useApplyPlan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (planId: string) => api<{ status: string }>(`/ai/plans/${planId}/apply`, { method: 'POST' }),
    onSuccess: () => invalidate(keys.today, keys.tasks),
  });
}
