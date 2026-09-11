'use client';

import React, { useState, useEffect } from 'react';
import { Account } from '@/types/domain';
import { useUpdateAccount, useDeleteAccount } from '@/hooks/useFinance';

interface AccountManageModalProps {
  account: Account | null;
  isOpen: boolean;
  onClose: () => void;
}

export function AccountManageModal({
  account,
  isOpen,
  onClose,
}: AccountManageModalProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState('checking');
  const [currency, setCurrency] = useState('UZS');
  const [balance, setBalance] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const updateAccountMutation = useUpdateAccount();
  const deleteAccountMutation = useDeleteAccount();

  useEffect(() => {
    if (account) {
      setName(account.name || '');
      setType(account.type || 'checking');
      setCurrency(account.currency || 'UZS');
      const minor =
        account.balance_minor ??
        (account as any).current_balance_minor ??
        ((account as any).balance ? Math.round((account as any).balance * 100) : 0);
      setBalance(String(minor / 100));
      setIsDeleting(false);
      setErrorMsg(null);
    }
  }, [account]);

  if (!isOpen || !account) return null;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Укажите название счёта');
      return;
    }

    const balVal = parseFloat(balance.replace(',', '.')) || 0;
    const balance_minor = Math.round(balVal * 100);

    try {
      await updateAccountMutation.mutateAsync({
        accountId: account.id,
        input: {
          name: name.trim(),
          type,
          currency,
          balance_minor,
        },
      });
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Ошибка обновления счёта');
    }
  };

  const handleDelete = async () => {
    try {
      await deleteAccountMutation.mutateAsync(account.id);
      setIsDeleting(false);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось удалить счёт');
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
              Редактирование параметров карты/счёта и остатка
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary p-1 rounded-lg text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {isDeleting ? (
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-3">
            <p className="text-xs font-semibold text-rose-600 dark:text-rose-400">
              Вы уверены, что хотите безвозвратно удалить счёт «{account.name}»?
            </p>
            <p className="text-[11px] text-text-muted">
              Счёт будет удален из системы. Это действие нельзя отменить.
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
                {deleteAccountMutation.isPending ? 'Удаление...' : 'Да, удалить'}
              </button>
            </div>
          </div>
        ) : (
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

            <div>
              <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                Текущий баланс ({currency})
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
                className="w-full text-xs font-mono font-bold px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {errorMsg && (
              <div className="p-2.5 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-600 dark:text-rose-400 text-xs">
                {errorMsg}
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setIsDeleting(true)}
                className="text-xs font-semibold text-rose-600 hover:text-rose-700 dark:text-rose-400 p-1 rounded transition-colors"
              >
                Удалить счёт
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
        )}
      </div>
    </div>
  );
}
