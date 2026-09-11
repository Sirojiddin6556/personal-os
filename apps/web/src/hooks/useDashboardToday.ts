'use client';

import { useState } from 'react';
import { Task, TaskStatus, CalendarEvent, BudgetSummary } from '@/types/domain';

import { MorningBrief } from '@/types/ai';

export function useDashboardToday() {
  const [brief, setBrief] = useState<MorningBrief | null>({
    id: 'brief-today',
    date: new Date().toISOString().split('T')[0],
    stats: {
      events_count: 2,
      tasks_count: 4,
      free_hours: 3.5,
      critical_tasks_count: 1,
    },
    proposed_schedule: [
      { id: 'sb-1', time: '09:30 — 11:00', title: 'Фокус: Подготовка отчета по выручке', type: 'task' },
      { id: 'sb-2', time: '11:30 — 12:30', title: 'Team Sync (Встреча)', type: 'meeting' },
      { id: 'sb-3', time: '14:00 — 15:30', title: 'Миграция БД PostgreSQL', type: 'task' },
    ],
    ai_comment:
      'Начните с квартального отчёта до 11:00 — после начнётся командный митинг и фокусное время сократится.',
  });

  const [topTasks] = useState<Task[]>([
    {
      id: 'task-1',
      title: 'Подготовить отчёт по квартальной выручке',
      status: 'in_progress',
      priority: 'high',
      due_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
      project: { id: 'p-work', name: 'work', color: '#6366f1' },
      subtasks: [
        { id: 's1', title: '1C выгрузка', completed: true },
        { id: 's2', title: 'P&L таблица', completed: false },
      ],
      sort_order: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'task-2',
      title: 'Запустить миграцию базы данных PostgreSQL 16',
      status: TaskStatus.TODO,
      priority: 'critical',
      due_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), // Overdue
      project: { id: 'p-infra', name: 'infra', color: '#ef4444' },
      sort_order: 2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'task-4',
      title: 'Ревью архитектуры UI компонентов (PR #42)',
      status: TaskStatus.INBOX,
      priority: 'high',
      due_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
      project: { id: 'p-frontend', name: 'frontend', color: '#0ea5e9' },
      sort_order: 3,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ]);

  const [overdueTasks] = useState<Task[]>([
    {
      id: 'task-2',
      title: 'Запустить миграцию базы данных PostgreSQL 16',
      status: TaskStatus.TODO,
      priority: 'critical',
      due_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
      project: { id: 'p-infra', name: 'infra', color: '#ef4444' },
      sort_order: 2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ]);

  const [agenda] = useState<CalendarEvent[]>([
    {
      id: 'ev-1',
      title: 'Daily Standup с продуктовой командой',
      start_time: '2026-09-11T10:00:00Z',
      end_time: '2026-09-11T10:30:00Z',
      start: '10:00',
      end: '10:30',
      is_external: false,
      color: '#0ea5e9',
    },
    {
      id: 'ev-2',
      title: 'Team Sync (Google Calendar)',
      start_time: '2026-09-11T11:30:00Z',
      end_time: '2026-09-11T12:30:00Z',
      start: '11:30',
      end: '12:30',
      is_external: true,
      color: '#6366f1',
    },
    {
      id: 'ev-3',
      title: 'Архитектурный синк по Personal OS',
      start_time: '2026-09-11T16:00:00Z',
      end_time: '2026-09-11T17:00:00Z',
      start: '16:00',
      end: '17:00',
      is_external: false,
      color: '#10b981',
    },
  ]);

  const [budgetSummary] = useState<BudgetSummary>({
    daily_spent_minor: 120000,
    monthly_spent_minor: 4250000,
    monthly_limit_minor: 6000000,
    spent: 42500,
    limit: 60000,
    currency: 'RUB',
    percentage: 71,
    remaining: 17500,
    category: 'Все категории',
  });


  const dismissBrief = () => setBrief(null);

  return {
    brief,
    dismissBrief,
    topTasks,
    overdueTasks,
    agenda,
    budgetSummary,
    stats: {
      totalTasks: 7,
      completedTasks: 3,
      overdueCount: overdueTasks.length,
      eventsCount: agenda.length,
      freeHours: 3.5,
    },
  };
}
