/**
 * @file query-keys.ts
 * @description Centralized TanStack Query key factory for cache management and targeted invalidations.
 * Structured hierarchically according to the Frontend Architecture specification.
 */

export const queryKeys = {
  /**
   * Tasks and Kanban cache keys.
   */
  tasks: {
    all: ['tasks'] as const,
    list: (filters?: Record<string, unknown>) =>
      [...queryKeys.tasks.all, 'list', filters] as const,
    detail: (id: string) =>
      [...queryKeys.tasks.all, 'detail', id] as const,
  },

  /**
   * Calendar schedule, events, time blocks, and Google sync keys.
   */
  calendar: {
    all: ['calendar'] as const,
    events: (range?: { from?: string; to?: string; start?: string; end?: string }) =>
      [...queryKeys.calendar.all, 'events', range] as const,
    timeBlocks: (date?: string) =>
      [...queryKeys.calendar.all, 'timeBlocks', date] as const,
    syncStatus: () =>
      [...queryKeys.calendar.all, 'syncStatus'] as const,
  },

  /**
   * Financial accounts, transaction ledger, budgets, and balance summaries.
   */
  finance: {
    all: ['finance'] as const,
    accounts: () =>
      [...queryKeys.finance.all, 'accounts'] as const,
    categories: () =>
      [...queryKeys.finance.all, 'categories'] as const,
    transactions: (filters?: Record<string, unknown>) =>
      [...queryKeys.finance.all, 'transactions', filters] as const,
    budgets: (month?: string) =>
      [...queryKeys.finance.all, 'budgets', month] as const,
    summary: () =>
      [...queryKeys.finance.all, 'summary'] as const,
  },

  /**
   * Dashboard composite views (Today screen).
   */
  dashboard: {
    all: ['dashboard'] as const,
    today: () =>
      [...queryKeys.dashboard.all, 'today'] as const,
  },

  /**
   * Notes and semantic knowledge base.
   */
  notes: {
    all: ['notes'] as const,
    list: (filters?: Record<string, unknown>) =>
      [...queryKeys.notes.all, 'list', filters] as const,
    detail: (id: string) =>
      [...queryKeys.notes.all, 'detail', id] as const,
  },

  /**
   * AI Advisor recommendations, proposed plans, and chat context.
   */
  advisor: {
    all: ['advisor'] as const,
    plans: () =>
      [...queryKeys.advisor.all, 'plans'] as const,
    planDetail: (id: string) =>
      [...queryKeys.advisor.all, 'plans', id] as const,
  },

  /**
   * Habit tracker streaks and logs.
   */
  habits: {
    all: ['habits'] as const,
    list: () =>
      [...queryKeys.habits.all, 'list'] as const,
    detail: (id: string) =>
      [...queryKeys.habits.all, 'detail', id] as const,
  },

  /**
   * User notification feeds and badge counters.
   */
  notifications: {
    all: ['notifications'] as const,
    list: (filters?: Record<string, unknown>) =>
      [...queryKeys.notifications.all, 'list', filters] as const,
    unreadCount: () =>
      [...queryKeys.notifications.all, 'unreadCount'] as const,
  },
} as const;
