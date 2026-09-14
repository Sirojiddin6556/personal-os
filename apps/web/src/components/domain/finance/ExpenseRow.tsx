'use client';

import React from 'react';
import { Transaction } from '@/types/domain';
import { cn, formatCurrency, formatDateShort } from '@/lib/utils';

export interface ExpenseRowProps {
  transaction: Transaction;
  onClick?: (id: string) => void;
}

export function ExpenseRow({ transaction, onClick }: ExpenseRowProps) {
  const isIncome = transaction.type === 'income';

  // Category Icon Default Fallback
  const renderCategoryIcon = () => {
    if (isIncome) {
      return (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
          <polyline points="17 6 23 6 23 12" />
        </svg>
      );
    }
    // Expense icon
    return (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
        <line x1="6" y1="1" x2="6" y2="4" />
        <line x1="10" y1="1" x2="10" y2="4" />
        <line x1="14" y1="1" x2="14" y2="4" />
      </svg>
    );
  };

  const amountValue =
    transaction.amount ??
    (transaction.amount_minor !== undefined ? transaction.amount_minor / 100 : 0);
  const amountSign = isIncome ? amountValue : -Math.abs(amountValue);
  const dateStr = transaction.occurred_at || transaction.date || transaction.transaction_date || new Date().toISOString();

  return (
    <div
      onClick={() => onClick?.(transaction.id)}
      className={cn(
        'flex items-center justify-between p-3.5 bg-surface hover:bg-surface-muted/70 border-b border-border last:border-0 transition-colors duration-fast select-none',
        onClick && 'cursor-pointer'
      )}
    >
      {/* Left: Category Icon + Details */}
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={cn(
            'flex items-center justify-center w-10 h-10 rounded-xl shrink-0 shadow-2xs',
            isIncome
              ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-300'
              : 'bg-rose-50 text-rose-600 dark:bg-rose-950/80 dark:text-rose-300'
          )}
        >
          {renderCategoryIcon()}
        </div>

        <div className="truncate">
          <p className="text-sm font-semibold text-text-primary truncate">
            {transaction.description || transaction.category || 'Без описания'}
          </p>
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <span className="font-medium text-text-secondary">{transaction.category || 'Общие'}</span>
            <span>•</span>
            <span className="text-text-muted">{transaction.account_name || 'Счёт'}</span>
          </div>
        </div>
      </div>

      {/* Right: Formatted Amount + Date */}
      <div className="text-right shrink-0 ml-4">
        <p
          className={cn(
            'text-sm font-bold font-mono tracking-tight',
            isIncome
              ? 'text-emerald-600 dark:text-emerald-400'
              : 'text-rose-600 dark:text-rose-400'
          )}
        >
          {formatCurrency(amountSign, transaction.currency || 'UZS')}
        </p>
        <p className="text-[11px] text-text-muted mt-0.5">
          {formatDateShort(dateStr)}
        </p>
      </div>
    </div>
  );

}

export default ExpenseRow;
