'use client';

import React, { useState } from 'react';
import { AIPreviewPlan } from '@/types/ai';
import { cn } from '@/lib/utils';

export interface AIPreviewDiffProps {
  plan: AIPreviewPlan;
  onConfirm: () => void;
  onReject: () => void;
  onPartialApply: (selectedIds: string[]) => void;
}

export function AIPreviewDiff({
  plan,
  onConfirm,
  onReject,
  onPartialApply,
}: AIPreviewDiffProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(
    plan.changes.map((c) => c.id)
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedIds(plan.changes.map((c) => c.id));
  const deselectAll = () => setSelectedIds([]);

  const isAllSelected = selectedIds.length === plan.changes.length;
  const isNoneSelected = selectedIds.length === 0;

  const confidencePercent =
    plan.confidence <= 1 ? Math.round(plan.confidence * 100) : plan.confidence;

  return (
    <div
      role="region"
      aria-label="Предварительный просмотр действий AI"
      className="flex flex-col border border-border bg-surface rounded-2xl overflow-hidden shadow-lg transition-all"
    >
      {/* Header with AI badge and confidence */}
      <div className="flex flex-wrap items-center justify-between px-5 py-3.5 bg-slate-50 dark:bg-slate-900/80 border-b border-border gap-3">
        <div className="flex items-center gap-2.5">
          <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
          </span>
          <div>
            <h3 className="text-sm font-bold text-text-primary">{plan.title}</h3>
            {plan.description && (
              <p className="text-xs text-text-secondary">{plan.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            Уверенность AI: {confidencePercent}%
          </span>
        </div>
      </div>

      {/* Toolbar: Select All / Deselect */}
      <div className="flex items-center justify-between px-5 py-2.5 bg-surface-muted/60 border-b border-border text-xs text-text-secondary">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isAllSelected}
            onChange={() => (isAllSelected ? deselectAll() : selectAll())}
            aria-label="Выбрать все предложения"
            className="w-4 h-4 rounded border-border text-primary focus:ring-primary/20 cursor-pointer"
          />
          <span className="font-medium">
            Выбрано {selectedIds.length} из {plan.changes.length} предложений
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs font-medium">
          <button
            type="button"
            onClick={selectAll}
            className="hover:text-primary transition-colors"
          >
            Выбрать все
          </button>
          <span>•</span>
          <button
            type="button"
            onClick={deselectAll}
            className="hover:text-primary transition-colors"
          >
            Снять выбор
          </button>
        </div>
      </div>

      {/* Diff Changes List */}
      <div className="divide-y divide-border p-4 space-y-3 overflow-y-auto max-h-[420px]">
        {plan.changes.map((change) => {
          const isSelected = selectedIds.includes(change.id);
          return (
            <div
              key={change.id}
              className={cn(
                'pt-3 first:pt-0 rounded-xl p-3 transition-colors duration-fast',
                isSelected ? 'bg-primary/5' : 'opacity-60 bg-transparent'
              )}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelect(change.id)}
                  aria-label={`Применить: ${change.title}`}
                  className="mt-1 w-4 h-4 rounded border-border text-primary focus:ring-primary/20 cursor-pointer"
                />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-bold text-text-primary truncate">
                      {change.title}
                    </span>
                    {change.conflict_resolved && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-200">
                        Конфликт разрешён
                      </span>
                    )}
                  </div>

                  {/* Before vs After Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    {/* Before / Current */}
                    {change.before && (
                      <div className="p-2 rounded-lg bg-rose-50/70 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-text-secondary">
                        <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 block mb-0.5">
                          Было:
                        </span>
                        <p className="line-through text-slate-500 dark:text-slate-400">
                          {change.before}
                        </p>
                      </div>
                    )}

                    {/* After / Proposed */}
                    {change.after && (
                      <div className="p-2 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/60 text-text-primary">
                        <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 block mb-0.5">
                          Предлагается:
                        </span>
                        <p className="font-semibold text-emerald-800 dark:text-emerald-300">
                          ✓ {change.after}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between px-5 py-3.5 bg-slate-50 dark:bg-slate-900/80 border-t border-border gap-3">
        <span className="text-xs text-text-muted">
          Безопасное применение: действие обратимо через Undo
        </span>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReject}
            className="px-3.5 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-lg transition-colors"
          >
            Отклонить всё
          </button>

          {!isAllSelected && !isNoneSelected && (
            <button
              type="button"
              onClick={() => onPartialApply(selectedIds)}
              className="px-4 py-2 text-xs font-bold text-primary border border-primary/40 hover:bg-primary/10 rounded-lg transition-colors"
            >
              Применить выбранные ({selectedIds.length})
            </button>
          )}

          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 text-xs font-bold text-white bg-primary hover:bg-primary-600 active:scale-95 rounded-lg shadow-sm transition-all"
          >
            Аппликовать всё
          </button>
        </div>
      </div>
    </div>
  );
}

export default AIPreviewDiff;
