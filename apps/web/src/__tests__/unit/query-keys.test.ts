import { describe, it, expect } from 'vitest';
import { queryKeys } from '@/lib/query-keys';

describe('queryKeys factory', () => {
  describe('tasks keys', () => {
    it('produces hierarchical tasks keys', () => {
      expect(queryKeys.tasks.all).toEqual(['tasks']);
      expect(queryKeys.tasks.list()).toEqual(['tasks', 'list', undefined]);
      expect(queryKeys.tasks.list({ status: 'todo', priority: 'high' })).toEqual([
        'tasks',
        'list',
        { status: 'todo', priority: 'high' },
      ]);
      expect(queryKeys.tasks.detail('task-100')).toEqual(['tasks', 'detail', 'task-100']);
    });
  });

  describe('calendar keys', () => {
    it('produces calendar event and timeblock keys', () => {
      expect(queryKeys.calendar.all).toEqual(['calendar']);
      const range = { from: '2026-09-01', to: '2026-09-30' };
      expect(queryKeys.calendar.events(range)).toEqual(['calendar', 'events', range]);
      expect(queryKeys.calendar.timeBlocks('2026-09-11')).toEqual([
        'calendar',
        'timeBlocks',
        '2026-09-11',
      ]);
      expect(queryKeys.calendar.syncStatus()).toEqual(['calendar', 'syncStatus']);
    });
  });

  describe('finance keys', () => {
    it('produces finance accounts, transactions, budgets, and summary keys', () => {
      expect(queryKeys.finance.all).toEqual(['finance']);
      expect(queryKeys.finance.accounts()).toEqual(['finance', 'accounts']);
      const txFilters = { account_id: 'acc-1', type: 'expense' };
      expect(queryKeys.finance.transactions(txFilters)).toEqual([
        'finance',
        'transactions',
        txFilters,
      ]);
      expect(queryKeys.finance.budgets('2026-09')).toEqual(['finance', 'budgets', '2026-09']);
      expect(queryKeys.finance.summary()).toEqual(['finance', 'summary']);
    });
  });

  describe('dashboard keys', () => {
    it('produces dashboard today key', () => {
      expect(queryKeys.dashboard.all).toEqual(['dashboard']);
      expect(queryKeys.dashboard.today()).toEqual(['dashboard', 'today']);
    });
  });

  describe('knowledge notes keys', () => {
    it('produces notes list and detail keys', () => {
      expect(queryKeys.notes.all).toEqual(['notes']);
      expect(queryKeys.notes.list({ q: 'architecture' })).toEqual([
        'notes',
        'list',
        { q: 'architecture' },
      ]);
      expect(queryKeys.notes.detail('note-55')).toEqual(['notes', 'detail', 'note-55']);
    });
  });

  describe('ai advisor keys', () => {
    it('produces advisor plans keys', () => {
      expect(queryKeys.advisor.all).toEqual(['advisor']);
      expect(queryKeys.advisor.plans()).toEqual(['advisor', 'plans']);
      expect(queryKeys.advisor.planDetail('plan-9')).toEqual(['advisor', 'plans', 'plan-9']);
    });
  });

  describe('habits and notifications keys', () => {
    it('produces habits and notifications keys correctly', () => {
      expect(queryKeys.habits.all).toEqual(['habits']);
      expect(queryKeys.habits.list()).toEqual(['habits', 'list']);
      expect(queryKeys.habits.detail('habit-1')).toEqual(['habits', 'detail', 'habit-1']);

      expect(queryKeys.notifications.all).toEqual(['notifications']);
      expect(queryKeys.notifications.list({ unread_only: true })).toEqual([
        'notifications',
        'list',
        { unread_only: true },
      ]);
      expect(queryKeys.notifications.unreadCount()).toEqual(['notifications', 'unreadCount']);
    });
  });
});
