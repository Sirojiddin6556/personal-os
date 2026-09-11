'use client';

import React from 'react';
import { Budget } from '@/types/domain';
import { formatMinorUnits, getCategoryColor } from '@/lib/charts';
import { cn } from '@/lib/utils';

export interface BudgetGaugeRowProps {
  budget: Budget & {
    spent_minor?: number;
    category_name?: string;
    category_icon?: string;
  };
  onClick?: (budget: Budget) => void;
  className?: string;
}

export function BudgetGaugeRow({
  budget,
  onClick,
  className,
}: BudgetGaugeRowProps) {
  const spentMinor = budget.spent_minor ?? budget.current_spent_minor ?? 0;
  const limitMinor = budget.limit_minor ?? 1;
  const currency = budget.currency || 'UZS';
  const categoryName = budget.category_name || budget.category_id || 'Общие расходы';

  const percent = limitMinor > 0 ? Math.round((spentMinor / limitMinor) * 100) : 0;
  const isOverflow = percent > 100;
  const remainingMinor = Math.max(0, limitMinor - spentMinor);
  const overspentMinor = isOverflow ? spentMinor - limitMinor : 0;

  // Threshold colors: <70% success, 70-90% warning, >90% error, >100% critical
  let statusTier: 'success' | 'warning' | 'error' | 'critical' = 'success';
  if (percent > 100) {
    statusTier = 'critical';
  } else if (percent > 90) {
    statusTier = 'error';
  } else if (percent >= 70) {
    statusTier = 'warning';
  }

  const barColor = {
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    error: 'bg-rose-500',
    critical: 'bg-red-600 animate-pulse',
  }[statusTier];

  const badgeStyles = {
    success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    error: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    critical: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 border-red-300 dark:border-red-700 font-bold',
  }[statusTier];

  const categoryColor = getCategoryColor(categoryName);

  return (
    <div
      role="row"
      onClick={() => onClick?.(budget)}
      className={cn(
        'group flex flex-col p-3.5 bg-surface hover:bg-surface-muted/60 border border-border rounded-xl transition-all select-none',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {/* Top Row: Category Identity + Percentage Badge */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0 shadow-2xs"
            style={{ backgroundColor: categoryColor }}
          />
          <span className="text-sm font-semibold text-text-primary truncate">
            {categoryName}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isOverflow && (
            <span className="text-[10px] font-bold text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-950/80 px-2 py-0.5 rounded-full uppercase tracking-wider animate-bounce">
              Перерасход!
            </span>
          )}
          <span
            className={cn(
              'text-xs font-mono font-bold px-2 py-0.5 rounded-md border',
              badgeStyles
            )}
          >
            {percent}%
          </span>
        </div>
      </div>

      {/* Progress Bar with WAI-ARIA Semantics */}
      <div
        role="progressbar"
        aria-valuenow={Math.min(percent, 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${percent}% израсходовано. Потрачено: ${formatMinorUnits(spentMinor, currency)} из лимита ${formatMinorUnits(limitMinor, currency)}`}
        className="w-full h-2.5 bg-surface-muted rounded-full overflow-hidden border border-border/50 relative"
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            barColor
          )}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>

      {/* Bottom Subline / Tooltip Breakdown */}
      <div className="flex items-center justify-between text-xs text-text-muted mt-2 pt-1 font-mono">
        <div className="flex items-center gap-1.5 truncate">
          <span className="text-text-secondary font-medium">
            {formatMinorUnits(spentMinor, currency)}
          </span>
          <span>/</span>
          <span className="text-text-muted">
            {formatMinorUnits(limitMinor, currency)}
          </span>
        </div>

        <div>
          {isOverflow ? (
            <span className="text-red-600 dark:text-red-400 font-semibold text-[11px]">
              + {formatMinorUnits(overspentMinor, currency)}
            </span>
          ) : (
            <span className="text-text-secondary text-[11px]">
              Остаток: <strong className="text-emerald-600 dark:text-emerald-400">{formatMinorUnits(remainingMinor, currency)}</strong>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default BudgetGaugeRow;
