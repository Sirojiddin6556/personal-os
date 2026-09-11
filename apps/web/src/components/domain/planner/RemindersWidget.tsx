'use client';

import React, { useState } from 'react';
import {
  PlannerReminder,
  useCreateReminder,
  useDismissReminder,
  useNotificationReminders,
} from '@/hooks/usePlanner';

interface RemindersWidgetProps {
  reminders: PlannerReminder[];
  targetDate: string;
}

export function RemindersWidget({ reminders, targetDate }: RemindersWidgetProps) {
  const { requestPermission, hasPermission } = useNotificationReminders();
  const createMutation = useCreateReminder();
  const dismissMutation = useDismissReminder();

  const [isAdding, setIsAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [remindTime, setRemindTime] = useState('09:00');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    // Combine targetDate + remindTime
    const isoDateTime = `${targetDate}T${remindTime}:00Z`;

    await createMutation.mutateAsync({
      title: title.trim(),
      remind_at: isoDateTime,
      remind_type: 'custom',
    });
    setTitle('');
    setIsAdding(false);
  };

  const handleQuickAdd = async (offsetMinutes: number, label: string) => {
    const future = new Date(Date.now() + offsetMinutes * 60000);
    await createMutation.mutateAsync({
      title: label,
      remind_at: future.toISOString(),
      remind_type: 'custom',
    });
  };

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold text-sm">
            🔔
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-primary">Напоминания</h3>
            <p className="text-xs text-text-muted">
              {reminders.length} активных напоминаний
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsAdding(!isAdding)}
          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-surface-muted hover:bg-surface-elevated text-text-primary transition-colors"
        >
          {isAdding ? 'Отмена' : '+ Напомнить'}
        </button>
      </div>

      {/* Permission banner */}
      {!hasPermission && (
        <div className="p-3 bg-primary/10 border border-primary/20 rounded-xl flex items-center justify-between gap-3">
          <div className="text-xs text-text-primary">
            <span className="font-bold">Включите Push-уведомления</span>, чтобы получать всплывающие напоминания в браузере.
          </div>
          <button
            onClick={() => requestPermission()}
            className="px-2.5 py-1 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary-600 shrink-0"
          >
            Включить
          </button>
        </div>
      )}

      {/* Quick Reminder Shortcuts */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[11px] text-text-muted">Быстро:</span>
        <button
          onClick={() => handleQuickAdd(15, 'Проверить текущие задачи')}
          className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-surface-muted hover:bg-surface-elevated text-text-secondary transition-colors"
        >
          +15 мин
        </button>
        <button
          onClick={() => handleQuickAdd(30, 'Сделать перерыв и разминку')}
          className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-surface-muted hover:bg-surface-elevated text-text-secondary transition-colors"
        >
          +30 мин
        </button>
        <button
          onClick={() => handleQuickAdd(60, 'Фокус-блок 1 час')}
          className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-surface-muted hover:bg-surface-elevated text-text-secondary transition-colors"
        >
          +1 час
        </button>
      </div>

      {/* Create form */}
      {isAdding && (
        <form onSubmit={handleCreate} className="p-3 bg-surface-muted rounded-xl space-y-3">
          <input
            type="text"
            placeholder="О чем напомнить (например: Позвонить клиенту, выпить воды)..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-1.5 text-xs bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary"
            autoFocus
          />
          <div className="flex items-center justify-between gap-2">
            <input
              type="time"
              value={remindTime}
              onChange={(e) => setRemindTime(e.target.value)}
              className="px-2 py-1 text-xs bg-surface border border-border rounded-lg text-text-secondary"
            />
            <button
              type="submit"
              disabled={createMutation.isPending || !title.trim()}
              className="px-3 py-1 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 disabled:opacity-50"
            >
              Установить
            </button>
          </div>
        </form>
      )}

      {/* Reminders List */}
      <div className="space-y-2">
        {reminders.length === 0 && !isAdding ? (
          <p className="text-center py-3 text-xs text-text-muted">
            Нет активных напоминаний.
          </p>
        ) : (
          reminders.map((r) => {
            const timeFormatted = new Date(r.remind_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            });
            return (
              <div
                key={r.id}
                className="flex items-center justify-between p-2.5 rounded-xl bg-surface border border-border hover:border-border-subtle transition-all"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 shrink-0">
                    {timeFormatted}
                  </span>
                  <span className="text-xs font-medium text-text-primary truncate">
                    {r.title}
                  </span>
                </div>

                <button
                  onClick={() => dismissMutation.mutate(r.id)}
                  className="px-2 py-0.5 text-[11px] font-semibold rounded bg-surface-muted hover:bg-surface-elevated text-text-muted hover:text-text-primary transition-colors shrink-0"
                >
                  OK
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
