'use client';

import React, { useState } from 'react';
import { Transaction } from '@/types/domain';
import { useReverseTransaction } from '@/hooks/useFinance';
import { formatMinorUnits } from '@/lib/charts';
import { formatDateShort } from '@/lib/utils';

interface TransactionDetailModalProps {
  transaction: Transaction | null;
  isOpen: boolean;
  onClose: () => void;
}

export function TransactionDetailModal({
  transaction,
  isOpen,
  onClose,
}: TransactionDetailModalProps) {
  const [reversalReason, setReversalReason] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const reverseTxMutation = useReverseTransaction();

  if (!isOpen || !transaction) return null;

  const isIncome = String(transaction.type) === 'income';
  const amountMinor =
    transaction.amount_minor ??
    (transaction.amount ? Math.round(transaction.amount * 100) : 0);

  const handleReverse = async () => {
    try {
      await reverseTxMutation.mutateAsync({
        transaction_id: transaction.id,
        reason: reversalReason.trim() || 'Сторнирование пользователем',
      });
      setShowConfirm(false);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось отменить операцию');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fadeIn">
      <div
        className="w-full max-w-md bg-surface border border-border rounded-2xl shadow-xl p-5 sm:p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div>
            <h2 className="text-base font-bold text-text-primary">
              Детали операции
            </h2>
            <p className="text-xs text-text-secondary mt-0.5">
              Информация о транзакции и управление
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary p-1 rounded-lg text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Amount Banner */}
        <div className="p-4 rounded-xl bg-surface-muted border border-border/80 text-center space-y-1">
          <span className="text-[11px] uppercase tracking-wider font-semibold text-text-muted">
            {isIncome ? 'Поступление' : 'Расход'}
          </span>
          <p
            className={`text-2xl font-extrabold font-mono ${
              isIncome
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-600 dark:text-rose-400'
            }`}
          >
            {isIncome ? '+' : '-'}
            {formatMinorUnits(amountMinor, transaction.currency || 'UZS')}
          </p>
          <p className="text-xs text-text-secondary font-medium">
            {transaction.description || transaction.category || 'Без описания'}
          </p>
        </div>

        {/* Details Grid */}
        <div className="space-y-2.5 text-xs">
          <div className="flex justify-between py-1.5 border-b border-border/60">
            <span className="text-text-secondary">Категория</span>
            <span className="font-semibold text-text-primary">
              {transaction.category || 'Общие расходы'}
            </span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-border/60">
            <span className="text-text-secondary">Счёт</span>
            <span className="font-semibold text-text-primary">
              {transaction.account_name || 'Основной счёт'}
            </span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-border/60">
            <span className="text-text-secondary">Дата операции</span>
            <span className="font-semibold text-text-primary">
              {formatDateShort(transaction.occurred_at || transaction.date || transaction.transaction_date || '')}
            </span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-border/60">
            <span className="text-text-secondary">Статус</span>
            <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              Проведено (Posted)
            </span>
          </div>
        </div>

        {errorMsg && (
          <div className="p-2.5 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-600 dark:text-rose-400 text-xs">
            {errorMsg}
          </div>
        )}

        {/* Reversal Confirmation */}
        {showConfirm ? (
          <div className="p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-3">
            <p className="text-xs text-rose-600 dark:text-rose-400 font-medium">
              Вы уверены, что хотите отменить (сторнировать) эту операцию? Баланс счёта будет автоматически скорректирован.
            </p>
            <input
              type="text"
              placeholder="Причина отмены (необязательно)"
              value={reversalReason}
              onChange={(e) => setReversalReason(e.target.value)}
              className="w-full text-xs px-3 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-surface-muted"
              >
                Назад
              </button>
              <button
                type="button"
                onClick={handleReverse}
                disabled={reverseTxMutation.isPending}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold disabled:opacity-50"
              >
                {reverseTxMutation.isPending ? 'Отмена...' : 'Подтвердить сторно'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setShowConfirm(true)}
              className="px-3 py-2 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 transition-colors"
            >
              Сторнировать / Отменить
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-surface-muted hover:bg-border text-text-primary text-xs font-semibold transition-colors"
            >
              Закрыть
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
