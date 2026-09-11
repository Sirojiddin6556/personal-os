'use client';

import React, { useState } from 'react';
import { MorningBrief } from '@/types/ai';
import { cn } from '@/lib/utils';

export interface MorningBriefCardProps {
  brief: MorningBrief;
  onAccept: () => void;
  onPartialAccept: (ids: string[]) => void;
  onDismiss: () => void;
}

export function MorningBriefCard({
  brief,
  onAccept,
  onPartialAccept,
  onDismiss,
}: MorningBriefCardProps) {
  const [selectedBlockIds, setSelectedBlockIds] = useState<string[]>(
    brief.proposed_schedule.map((b) => b.id)
  );
  const [showScheduleDetails, setShowScheduleDetails] = useState(false);

  const toggleBlock = (id: string) => {
    setSelectedBlockIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const { stats, proposed_schedule, ai_comment } = brief;

  const isAllSelected = selectedBlockIds.length === proposed_schedule.length;
  const isNoneSelected = selectedBlockIds.length === 0;

  return (
    <div
      role="region"
      aria-label="Утренний брифинг"
      className="relative overflow-hidden p-5 sm:p-6 bg-gradient-to-r from-primary-500/10 via-indigo-500/5 to-purple-500/10 border border-primary/20 rounded-2xl shadow-xs transition-all duration-normal"
    >
      {/* Decorative background glow */}
      <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 rounded-full bg-primary/10 blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col gap-4">
        {/* Top Header Row */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            {/* Sunrise / AI Icon */}
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-primary text-white shadow-md shrink-0">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-lg font-bold text-text-primary tracking-tight">
                  Доброе утро!
                </h2>
                <span className="px-2.5 py-0.5 text-[11px] font-semibold rounded-full bg-primary/20 text-primary-700 dark:text-primary-300">
                  {new Date().toLocaleDateString('ru-RU', {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long',
                  })}
                </span>
              </div>

              {/* Statistics Counters: N events, X tasks, Y hours free */}
              <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary mt-1">
                <span>План на сегодня:</span>
                <span className="inline-flex items-center gap-1 font-bold text-text-primary px-2 py-0.5 bg-surface rounded-md border border-border text-xs">
                  📋 {stats.tasks_count} задач
                  {stats.critical_tasks_count ? (
                    <span className="text-rose-600 font-extrabold">({stats.critical_tasks_count} критич.)</span>
                  ) : null}
                </span>
                <span className="inline-flex items-center gap-1 font-bold text-text-primary px-2 py-0.5 bg-surface rounded-md border border-border text-xs">
                  📅 {stats.events_count} встречи
                </span>
                <span className="inline-flex items-center gap-1 font-bold text-emerald-600 dark:text-emerald-400 px-2 py-0.5 bg-surface rounded-md border border-border text-xs">
                  ⏳ {stats.free_hours}ч свободно
                </span>
              </div>
            </div>
          </div>

          {/* Quick Action buttons */}
          <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
            <button
              type="button"
              onClick={onDismiss}
              className="px-3.5 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary hover:bg-surface rounded-xl border border-border transition-colors"
            >
              Скрыть
            </button>
            <button
              type="button"
              onClick={() => setShowScheduleDetails(!showScheduleDetails)}
              className="px-3.5 py-2 text-xs font-semibold text-primary hover:bg-primary/10 rounded-xl border border-primary/30 transition-colors"
            >
              {showScheduleDetails ? 'Свернуть расписание' : 'Расписание дня'}
            </button>
            <button
              type="button"
              onClick={onAccept}
              className="px-4 py-2 text-xs font-bold text-white bg-primary hover:bg-primary-600 active:scale-95 rounded-xl shadow-sm transition-all flex items-center gap-1.5"
            >
              <span>Принять план</span>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* AI Recommendation Box */}
        {ai_comment && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-surface/80 dark:bg-surface/60 backdrop-blur border border-primary/20 text-xs text-text-primary">
            <span className="text-amber-500 text-sm shrink-0">💡</span>
            <div className="leading-relaxed">
              <strong className="text-primary font-bold">Совет AI-ассистента: </strong>
              <span>{ai_comment}</span>
            </div>
          </div>
        )}

        {/* Proposed Schedule Time Blocks (Collapsible) */}
        {showScheduleDetails && proposed_schedule.length > 0 && (
          <div className="mt-2 pt-3 border-t border-primary/15 space-y-2 animate-in fade-in duration-200">
            <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
              <span className="font-bold">Предлагаемое распределение времени:</span>
              <span className="text-[11px] text-text-muted">
                Выберите блоки для включения в календарь
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {proposed_schedule.map((block) => {
                const isSelected = selectedBlockIds.includes(block.id);
                return (
                  <div
                    key={block.id}
                    onClick={() => toggleBlock(block.id)}
                    className={cn(
                      'p-2.5 rounded-xl border text-xs cursor-pointer transition-all duration-fast flex items-start gap-2 select-none',
                      isSelected
                        ? 'bg-surface border-primary/40 shadow-xs'
                        : 'bg-surface/50 border-border opacity-50'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // Handled by parent div
                      className="mt-0.5 w-3.5 h-3.5 rounded border-border text-primary focus:ring-0 cursor-pointer"
                    />
                    <div className="truncate">
                      <span className="font-mono text-[11px] font-bold text-primary block">
                        {block.time}
                      </span>
                      <span className="font-medium text-text-primary truncate block mt-0.5">
                        {block.title}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Partial Accept CTA */}
            {!isAllSelected && !isNoneSelected && (
              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => onPartialAccept(selectedBlockIds)}
                  className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary-600 transition-colors shadow-xs"
                >
                  Принять выбранные ({selectedBlockIds.length})
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MorningBriefCard;
