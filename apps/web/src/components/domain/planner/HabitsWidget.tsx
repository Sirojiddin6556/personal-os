'use client';

import React, { useState } from 'react';
import { Habit, useCreateHabit, useDeleteHabit, useToggleHabit } from '@/hooks/usePlanner';

interface HabitsWidgetProps {
  habits: Habit[];
  targetDate: string;
}

export function HabitsWidget({ habits, targetDate }: HabitsWidgetProps) {
  const toggleMutation = useToggleHabit();
  const createMutation = useCreateHabit();
  const deleteMutation = useDeleteHabit();

  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [frequency, setFrequency] = useState<'daily' | 'weekdays' | 'weekends' | 'weekly'>('daily');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await createMutation.mutateAsync({
      title: newTitle.trim(),
      frequency_type: frequency,
      target_count: 1,
    });
    setNewTitle('');
    setIsAdding(false);
  };

  const completedCount = habits.filter((h) => h.is_completed_today).length;
  const progressPercent = habits.length > 0 ? Math.round((completedCount / habits.length) * 100) : 0;

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
            ✨
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-primary">Привычки & Рутины</h3>
            <p className="text-xs text-text-muted">
              {completedCount} из {habits.length} выполнено ({progressPercent}%)
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsAdding(!isAdding)}
          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-surface-muted hover:bg-surface-elevated text-text-primary transition-colors"
        >
          {isAdding ? 'Отмена' : '+ Привычка'}
        </button>
      </div>

      {/* Progress Bar */}
      {habits.length > 0 && (
        <div className="w-full bg-surface-muted h-1.5 rounded-full overflow-hidden">
          <div
            className="bg-emerald-500 h-full rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Quick Add Form */}
      {isAdding && (
        <form onSubmit={handleCreate} className="p-3 bg-surface-muted rounded-xl space-y-3">
          <input
            type="text"
            placeholder="Название привычки (например: Зарядка 15 мин)..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="w-full px-3 py-1.5 text-xs bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary"
            autoFocus
          />
          <div className="flex items-center justify-between gap-2">
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as any)}
              className="px-2 py-1 text-xs bg-surface border border-border rounded-lg text-text-secondary"
            >
              <option value="daily">Каждый день</option>
              <option value="weekdays">По будням</option>
              <option value="weekends">По выходным</option>
              <option value="weekly">Раз в неделю</option>
            </select>
            <button
              type="submit"
              disabled={createMutation.isPending || !newTitle.trim()}
              className="px-3 py-1 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 disabled:opacity-50"
            >
              Сохранить
            </button>
          </div>
        </form>
      )}

      {/* Habits Checklist */}
      <div className="space-y-2">
        {habits.length === 0 && !isAdding ? (
          <div className="text-center py-4 text-xs text-text-muted">
            <p>Нет добавленных привычек на этот день.</p>
            <button
              onClick={() => setIsAdding(true)}
              className="text-primary font-semibold hover:underline mt-1 inline-block"
            >
              + Создать первую привычку
            </button>
          </div>
        ) : (
          habits.map((habit) => (
            <div
              key={habit.id}
              className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${
                habit.is_completed_today
                  ? 'bg-emerald-500/5 border-emerald-500/20 text-text-secondary'
                  : 'bg-surface border-border hover:border-border-subtle text-text-primary'
              }`}
            >
              <label className="flex items-center gap-3 cursor-pointer flex-1 select-none">
                <input
                  type="checkbox"
                  checked={habit.is_completed_today}
                  onChange={() =>
                    toggleMutation.mutate({ habitId: habit.id, date: targetDate })
                  }
                  className="w-4 h-4 rounded-sm text-emerald-600 border-border focus:ring-emerald-500 cursor-pointer"
                />
                <span className={`text-xs font-medium ${habit.is_completed_today ? 'line-through text-text-muted' : ''}`}>
                  {habit.title}
                </span>
              </label>

              <div className="flex items-center gap-2">
                {habit.current_streak > 0 && (
                  <span
                    className="flex items-center gap-1 text-[11px] font-bold px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400"
                    title={`Стрик: ${habit.current_streak} дней подряд! Рекорд: ${habit.best_streak}`}
                  >
                    🔥 {habit.current_streak}д
                  </span>
                )}
                <button
                  onClick={() => deleteMutation.mutate(habit.id)}
                  className="text-text-muted hover:text-rose-500 p-1 rounded-md transition-colors text-xs"
                  title="Удалить привычку"
                >
                  ✕
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
