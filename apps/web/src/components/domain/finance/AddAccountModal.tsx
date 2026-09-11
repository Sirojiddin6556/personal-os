'use client';

import React, { useState } from 'react';
import { useCreateAccount } from '@/hooks/useFinance';

interface AddAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const PRESET_ACCOUNTS = [
  { name: 'Uzcard (Капиталбанк)', type: 'checking', currency: 'UZS' },
  { name: 'Humo (Anorbank)', type: 'checking', currency: 'UZS' },
  { name: 'Uzum Bank (Депозит / Счёт)', type: 'savings', currency: 'UZS' },
  { name: 'Наличные UZS (Кошелёк)', type: 'cash', currency: 'UZS' },
  { name: 'Валютная карта Visa/Mastercard (USD)', type: 'savings', currency: 'USD' },
  { name: 'TBC Bank UZS', type: 'checking', currency: 'UZS' },
  { name: 'Ipak Yoli Bank', type: 'checking', currency: 'UZS' },
];

export function AddAccountModal({ isOpen, onClose }: AddAccountModalProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState('checking');
  const [currency, setCurrency] = useState('UZS');
  const [initialBalance, setInitialBalance] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const createAccountMutation = useCreateAccount();

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Укажите название счёта или карты');
      return;
    }

    const balVal = parseFloat(initialBalance.replace(',', '.')) || 0;
    const initial_balance_minor = Math.round(balVal * 100);

    try {
      await createAccountMutation.mutateAsync({
        name: name.trim(),
        type,
        currency,
        initial_balance_minor,
      });
      setName('');
      setInitialBalance('');
      setErrorMsg(null);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Ошибка создания счёта');
    }
  };

  const handleSelectPreset = (preset: (typeof PRESET_ACCOUNTS)[0]) => {
    setName(preset.name);
    setType(preset.type);
    setCurrency(preset.currency);
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
              Новый финансовый счёт
            </h2>
            <p className="text-xs text-text-secondary mt-0.5">
              Поддержка карт Узбекистана (Uzcard/Humo), банков и валют
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary p-1 rounded-lg text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Quick Presets */}
        <div>
          <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1.5">
            Быстрый выбор шаблона
          </label>
          <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
            {PRESET_ACCOUNTS.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => handleSelectPreset(p)}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-muted hover:bg-border text-text-secondary hover:text-text-primary transition-colors border border-border/70"
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
              Название счёта / карты *
            </label>
            <input
              type="text"
              required
              placeholder="Например: Капиталбанк Uzcard"
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
              Начальный остаток / Баланс
            </label>
            <input
              type="text"
              inputMode="decimal"
              placeholder="0 (например, 500000)"
              value={initialBalance}
              onChange={(e) => setInitialBalance(e.target.value)}
              className="w-full text-xs font-mono font-bold px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {errorMsg && (
            <div className="p-2.5 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-600 dark:text-rose-400 text-xs">
              {errorMsg}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-text-secondary hover:bg-surface-muted transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={createAccountMutation.isPending || !name.trim()}
              className="px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold disabled:opacity-50 transition-colors shadow-xs"
            >
              {createAccountMutation.isPending ? 'Создание...' : 'Создать счёт'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
