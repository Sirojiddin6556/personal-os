'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Account } from '@/types/domain';
import { useUpdateAccount, useDeleteAccount, useReconcileAccount } from '@/hooks/useFinance';
import { formatMinorUnits } from '@/lib/charts';

interface AccountManageModalProps {
  account: Account | null;
  isOpen: boolean;
  onClose: () => void;
}

function parseCurrencyInput(raw: string): number {
  if (!raw) return 0;
  let cleaned = raw.replace(/[\s\u00A0]+/g, '');
  // Handle both comma and period present (e.g. 1,250.50 or 1.250,50)
  if (cleaned.includes(',') && cleaned.includes('.')) {
    if (cleaned.lastIndexOf('.') > cleaned.lastIndexOf(',')) {
      cleaned = cleaned.replace(/,/g, '');
    } else {
      cleaned = cleaned.replace(/\./g, '').replace(/,/g, '.');
    }
  } else if (cleaned.includes(',')) {
    cleaned = cleaned.replace(/,/g, '.');
  }
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

export function AccountManageModal({
  account,
  isOpen,
  onClose,
}: AccountManageModalProps) {
  const [activeTab, setActiveTab] = useState<'settings' | 'reconcile'>('settings');
  const [name, setName] = useState('');
  const [type, setType] = useState('checking');
  const [currency, setCurrency] = useState('UZS');
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Reconciliation state
  const [actualBalanceInput, setActualBalanceInput] = useState('');
  const [reconcileReason, setReconcileReason] = useState('');
  const [isSubmittingReconcile, setIsSubmittingReconcile] = useState(false);

  const updateAccountMutation = useUpdateAccount();
  const deleteAccountMutation = useDeleteAccount();
  const reconcileMutation = useReconcileAccount();

  const currentMinor =
    account?.balance_minor ??
    (account as any)?.current_balance_minor ??
    ((account as any)?.balance ? Math.round((account as any).balance * 100) : 0);

  useEffect(() => {
    if (account) {
      setName(account.name || '');
      setType(account.type || 'checking');
      setCurrency(account.currency || 'UZS');
      setActualBalanceInput(String(currentMinor / 100));
      setReconcileReason('');
      setIsDeleting(false);
      setIsSubmittingReconcile(false);
      setErrorMsg(null);
      setSuccessMsg(null);
      setActiveTab('settings');
    }
  }, [account, currentMinor]);

  // Real-time calculation of reconciliation signed delta
  const actualVal = useMemo(() => parseCurrencyInput(actualBalanceInput), [actualBalanceInput]);
  const actualMinor = useMemo(() => Math.round(actualVal * 100), [actualVal]);
  const deltaMinor = useMemo(() => actualMinor - currentMinor, [actualMinor, currentMinor]);

  if (!isOpen || !account) return null;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Укажите название счёта');
      return;
    }

    try {
      await updateAccountMutation.mutateAsync({
        accountId: account.id,
        input: {
          name: name.trim(),
          type,
          currency,
        },
      });
      setSuccessMsg('Счёт успешно обновлён');
      setTimeout(() => onClose(), 800);
    } catch (err: any) {
      setErrorMsg(err.message || 'Ошибка обновления счёта');
    }
  };

  const handleReconcile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmittingReconcile || reconcileMutation.isPending) return;

    if (deltaMinor === 0) {
      setErrorMsg('Фактический остаток совпадает с расчётным. Корректирующая операция не требуется.');
      return;
    }

    setIsSubmittingReconcile(true);
    setErrorMsg(null);

    try {
      await reconcileMutation.mutateAsync({
        accountId: account.id,
        actual_balance_minor: actualMinor,
        reason: reconcileReason.trim() || 'Периодическая сверка остатка',
      });
      setSuccessMsg('Сверка успешно проведена. Корректирующая проводка создана.');
      setTimeout(() => onClose(), 1000);
    } catch (err: any) {
      setIsSubmittingReconcile(false);
      if (err.status === 412 || String(err.message).includes('412')) {
        setErrorMsg('412 Precondition Failed: Баланс счёта изменился после открытия формы. Пожалуйста, обновите данные.');
      } else if (err.status === 409 || String(err.message).includes('409')) {
        setErrorMsg('409 Conflict: Сверка отклонена из-за конфликта состояния счёта. Проверьте журнал транзакций.');
      } else {
        setErrorMsg(err.message || 'Ошибка выполнения сверки счёта');
      }
    }
  };

  const handleDelete = async () => {
    try {
      await deleteAccountMutation.mutateAsync(account.id);
      setIsDeleting(false);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось архивировать счёт');
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
              Управление счётом
            </h2>
            <p className="text-xs text-text-secondary mt-0.5">
              {account.name} · {formatMinorUnits(currentMinor, currency)}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Закрыть окно"
            className="text-text-muted hover:text-text-primary p-1 rounded-lg text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Tab Switcher: Settings vs Reconcile */}
        <div className="flex p-1 bg-surface-muted rounded-xl border border-border">
          <button
            type="button"
            onClick={() => { setActiveTab('settings'); setErrorMsg(null); setSuccessMsg(null); }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeTab === 'settings'
                ? 'bg-surface text-text-primary shadow-xs'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Параметры счёта
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('reconcile'); setErrorMsg(null); setSuccessMsg(null); }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeTab === 'reconcile'
                ? 'bg-surface text-text-primary shadow-xs'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Сверка остатка (Reconciliation)
          </button>
        </div>

        {errorMsg && (
          <div className="p-2.5 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-600 dark:text-rose-400 text-xs">
            {errorMsg}
          </div>
        )}

        {successMsg && (
          <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-700 dark:text-emerald-300 text-xs">
            {successMsg}
          </div>
        )}

        {isDeleting ? (
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-3">
            <p className="text-xs font-semibold text-rose-600 dark:text-rose-400">
              Вы уверены, что хотите архивировать счёт «{account.name}»?
            </p>
            <p className="text-[11px] text-text-muted">
              Счёт с транзакциями будет заархивирован для сохранения целостности финансовой истории.
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setIsDeleting(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-surface-muted"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteAccountMutation.isPending}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold disabled:opacity-50"
              >
                {deleteAccountMutation.isPending ? 'Архивация...' : 'Да, архивировать'}
              </button>
            </div>
          </div>
        ) : activeTab === 'settings' ? (
          <form onSubmit={handleUpdate} className="space-y-3.5">
            <div>
              <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                Название счёта / карты *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setErrorMsg(null);
                }}
                className="w-full text-xs px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                  Тип счёта
                </label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="w-full text-xs px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="checking">💳 Дебетовая карта / Счёт</option>
                  <option value="savings">🏦 Накопительный / Депозит</option>
                  <option value="cash">💵 Наличные (Кошелёк)</option>
                  <option value="investment">📈 Инвестиции</option>
                  <option value="crypto">₿ Криптовалюта</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                  Валюта
                </label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full text-xs font-mono font-bold px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="UZS">UZS (сум)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="RUB">RUB (₽)</option>
                </select>
              </div>
            </div>

            {/* Read-Only Balance Info Box */}
            <div className="p-3 bg-surface-muted border border-border rounded-xl flex items-center justify-between">
              <div>
                <span className="block text-[10px] uppercase tracking-wider font-semibold text-text-muted">Текущий остаток в системе</span>
                <span className="text-sm font-bold font-mono text-text-primary">
                  {formatMinorUnits(currentMinor, currency)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('reconcile')}
                className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
              >
                Сверить остаток →
              </button>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setIsDeleting(true)}
                className="text-xs font-semibold text-rose-600 hover:text-rose-700 dark:text-rose-400 p-1 rounded transition-colors"
              >
                Архивировать счёт
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 rounded-xl text-xs font-medium text-text-secondary hover:bg-surface-muted transition-colors"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={updateAccountMutation.isPending || !name.trim()}
                  className="px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold disabled:opacity-50 transition-colors shadow-xs"
                >
                  {updateAccountMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </div>
          </form>
        ) : (
          /* Reconciliation Form */
          <form onSubmit={handleReconcile} className="space-y-3.5">
            <div className="p-3 bg-blue-50/50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-xl space-y-1">
              <p className="text-xs font-semibold text-blue-900 dark:text-blue-300">
                Сверка остатка (Reconciliation)
              </p>
              <p className="text-[11px] text-blue-700 dark:text-blue-400">
                Прямое редактирование баланса запрещено. Введите фактический остаток по выписке — система автоматически рассчитает корректирующую проводку.
              </p>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                Фактический остаток на руках / в банке ({currency}) *
              </label>
              <input
                type="text"
                inputMode="decimal"
                required
                placeholder="Например: 1 500 000 или 1250.50"
                value={actualBalanceInput}
                onChange={(e) => {
                  setActualBalanceInput(e.target.value);
                  setErrorMsg(null);
                }}
                className="w-full text-xs font-mono font-bold px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Real-time Signed Delta Card */}
            <div className="p-3 bg-surface-muted border border-border rounded-xl space-y-1">
              <div className="flex justify-between text-xs text-text-secondary">
                <span>Баланс по книге учета:</span>
                <span className="font-mono">{formatMinorUnits(currentMinor, currency)}</span>
              </div>
              <div className="flex justify-between text-xs text-text-secondary">
                <span>Фактический остаток:</span>
                <span className="font-mono">{formatMinorUnits(actualMinor, currency)}</span>
              </div>
              <div className="flex justify-between text-xs font-bold pt-1 border-t border-border">
                <span>Корректирующая дельта:</span>
                <span className={`font-mono ${deltaMinor > 0 ? 'text-emerald-600 dark:text-emerald-400' : deltaMinor < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-text-muted'}`}>
                  {deltaMinor > 0 ? '+' : ''}{formatMinorUnits(deltaMinor, currency)}
                </span>
              </div>
            </div>

            {deltaMinor === 0 && (
              <div className="p-2.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-amber-700 dark:text-amber-300 text-xs">
                Фактический остаток совпадает с расчётным (дельта 0). Корректирующая операция не требуется.
              </div>
            )}

            <div>
              <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                Причина корректировки / комментарий
              </label>
              <input
                type="text"
                placeholder="Например: Сверка по банковской выписке на конец месяца"
                value={reconcileReason}
                onChange={(e) => setReconcileReason(e.target.value)}
                className="w-full text-xs px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setActiveTab('settings')}
                className="px-3.5 py-2 rounded-xl text-xs font-medium text-text-secondary hover:bg-surface-muted transition-colors"
              >
                Назад
              </button>
              <button
                type="submit"
                disabled={reconcileMutation.isPending || isSubmittingReconcile || deltaMinor === 0}
                className="px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold disabled:opacity-50 transition-colors shadow-xs"
              >
                {isSubmittingReconcile || reconcileMutation.isPending ? 'Проведение сверки...' : 'Подтвердить сверку'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default AccountManageModal;
