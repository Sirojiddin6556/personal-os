'use client';

import React, { useState } from 'react';
import { Priority, Task, TimeBlock } from '@/types/domain';
import { useCreateTimeBlock } from '@/hooks/useCalendar';
import { useCreateTask } from '@/hooks/useTasks';

interface HourlyAgendaGridProps {
  timeBlocks: TimeBlock[];
  tasks: Task[];
  targetDate: string;
}

const HOURS = Array.from({ length: 17 }, (_, i) => i + 7); // 07:00 to 23:00

export function HourlyAgendaGrid({ timeBlocks, tasks, targetDate }: HourlyAgendaGridProps) {
  const createBlockMutation = useCreateTimeBlock();
  const createTaskMutation = useCreateTask();

  const [selectedHour, setSelectedHour] = useState<number | null>(null);
  const [slotType, setSlotType] = useState<'task' | 'block'>('block');
  const [slotTitle, setSlotTitle] = useState('');

  const now = new Date();
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();
  const isToday = targetDate === now.toISOString().split('T')[0];

  const handleCreateSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slotTitle.trim() || selectedHour === null) return;

    const startH = String(selectedHour).padStart(2, '0');
    const endH = String(selectedHour + 1).padStart(2, '0');
    const startIso = `${targetDate}T${startH}:00:00Z`;
    const endIso = `${targetDate}T${endH}:00:00Z`;

    if (slotType === 'block') {
      await createBlockMutation.mutateAsync({
        label: slotTitle.trim(),
        starts_at: startIso,
        ends_at: endIso,
        is_fixed: true,
      });
    } else {
      await createTaskMutation.mutateAsync({
        title: slotTitle.trim(),
        due_date: startIso,
        priority: Priority.P2,
        estimated_duration_minutes: 60,
      });
    }

    setSlotTitle('');
    setSelectedHour(null);
  };

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-sm">
            📅
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-primary">Расписание дня (07:00 - 23:00)</h3>
            <p className="text-xs text-text-muted">Тайм-блоки, встречи и запланированные дела</p>
          </div>
        </div>

        <span className="text-xs font-mono text-text-muted bg-surface-muted px-2.5 py-1 rounded-lg">
          {targetDate}
        </span>
      </div>

      {/* Quick Add Modal/Form for slot */}
      {selectedHour !== null && (
        <form onSubmit={handleCreateSlot} className="p-3 bg-surface-muted border border-border rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-text-primary">
              Запланировать на {String(selectedHour).padStart(2, '0')}:00 - {String(selectedHour + 1).padStart(2, '0')}:00
            </span>
            <button
              type="button"
              onClick={() => setSelectedHour(null)}
              className="text-text-muted hover:text-text-primary text-xs"
            >
              ✕
            </button>
          </div>

          <input
            type="text"
            placeholder="Название дела или встречи..."
            value={slotTitle}
            onChange={(e) => setSlotTitle(e.target.value)}
            className="w-full px-3 py-1.5 text-xs bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-hidden"
            autoFocus
          />

          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
                <input
                  type="radio"
                  name="slotType"
                  checked={slotType === 'block'}
                  onChange={() => setSlotType('block')}
                />
                Тайм-блок
              </label>
              <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
                <input
                  type="radio"
                  name="slotType"
                  checked={slotType === 'task'}
                  onChange={() => setSlotType('task')}
                />
                Задача
              </label>
            </div>

            <button
              type="submit"
              disabled={!slotTitle.trim()}
              className="px-3 py-1 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 disabled:opacity-50"
            >
              Добавить в план
            </button>
          </div>
        </form>
      )}

      {/* Hourly Timeline */}
      <div className="relative border-t border-border mt-2 divide-y divide-border">
        {/* Current Time Indicator line */}
        {isToday && currentHour >= 7 && currentHour <= 23 && (
          <div
            className="absolute left-0 right-0 z-10 flex items-center pointer-events-none"
            style={{
              top: `${((currentHour - 7) * 60 + currentMinute) * (48 / 60)}px`,
            }}
          >
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500 -ml-1 shadow-sm" />
            <div className="flex-1 h-0.5 bg-rose-500 shadow-sm" />
            <span className="text-[10px] font-mono font-bold text-rose-500 bg-surface px-1 ml-1 rounded">
              Сейчас
            </span>
          </div>
        )}

        {HOURS.map((hour) => {
          const hourStr = `${String(hour).padStart(2, '0')}:00`;

          // Find time blocks in this hour
          const blocksInHour = timeBlocks.filter((tb) => {
            const startH = new Date(tb.starts_at).getUTCHours();
            return startH === hour;
          });

          // Find tasks in this hour
          const tasksInHour = tasks.filter((t) => {
            if (!t.due_at) return false;
            const dueH = new Date(t.due_at).getUTCHours();
            return dueH === hour;
          });

          const hasItems = blocksInHour.length > 0 || tasksInHour.length > 0;

          return (
            <div
              key={hour}
              onClick={() => setSelectedHour(hour)}
              className={`group flex items-start gap-3 py-2 px-1 min-h-[48px] hover:bg-surface-muted/50 cursor-pointer transition-colors rounded-lg ${
                selectedHour === hour ? 'bg-primary/5 ring-1 ring-primary/30' : ''
              }`}
            >
              <span className="w-12 text-xs font-mono font-semibold text-text-muted shrink-0 pt-0.5">
                {hourStr}
              </span>

              <div className="flex-1 flex flex-wrap gap-2 items-center">
                {blocksInHour.map((tb) => (
                  <div
                    key={tb.id}
                    className="px-3 py-1.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-700 dark:text-blue-300 text-xs font-semibold flex items-center gap-2 shadow-2xs"
                  >
                    <span>🕒 {tb.label || 'Тайм-блок'}</span>
                    <span className="text-[10px] opacity-75 font-mono">
                      {new Date(tb.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                      {new Date(tb.ends_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}

                {tasksInHour.map((task) => (
                  <div
                    key={task.id}
                    className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-2 shadow-2xs ${
                      task.status === 'done'
                        ? 'bg-surface-muted border-border text-text-muted line-through'
                        : 'bg-primary/10 border-primary/20 text-primary-700 dark:text-primary-300'
                    }`}
                  >
                    <span>✓ {task.title}</span>
                    {task.estimate_minutes && (
                      <span className="text-[10px] opacity-75">~{task.estimate_minutes}м</span>
                    )}
                  </div>
                ))}

                {!hasItems && (
                  <span className="text-[11px] text-text-muted opacity-0 group-hover:opacity-100 transition-opacity italic">
                    + Нажмите, чтобы запланировать дело
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
