'use client';

import React, { useState, useMemo } from 'react';
import {
  useAccounts,
  useBudgets,
  useCreateTransaction,
  useTransactions,
} from '@/hooks/useFinance';
import { Account, TransactionType } from '@/types/domain';
import { formatMinorUnits, getCategoryColor } from '@/lib/charts';
import { SpendingBarChart } from '@/components/charts/SpendingBarChart';
import { CategoryPieChart } from '@/components/charts/CategoryPieChart';
import { BudgetGaugeRow } from '@/components/charts/BudgetGaugeRow';
import { ExpenseRow } from '@/components/domain/finance/ExpenseRow';
import { cn } from '@/lib/utils';

export default function FinancePage() {
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('day');
  const [txSearch, setTxSearch] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState<'all' | 'expense' | 'income'>('all');

  // Quick Expense Form State
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [expenseAmount, setExpenseAmount] = useState<string>('');
  const [expenseCategory, setExpenseCategory] = useState<string>('Продукты');
  const [expenseDescription, setExpenseDescription] = useState<string>('');
  const [formSuccessMessage, setFormSuccessMessage] = useState<string | null>(null);

  // TanStack Query Hooks
  const { accounts, isLoading: accountsLoading } = useAccounts();
  const { budgets, isLoading: budgetsLoading } = useBudgets();
  const {
    transactions,
    isLoading: txLoading,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useTransactions({
    type: txTypeFilter === 'all' ? undefined : txTypeFilter,
  });

  const createTxMutation = useCreateTransaction();

  // Primary currency
  const primaryCurrency = accounts[0]?.currency || 'RUB';

  // Total Net Worth across accounts
  const totalBalanceMinor = useMemo(() => {
    return accounts.reduce((acc, a) => acc + (a.balance_minor || 0), 0);
  }, [accounts]);

  // Aggregate SpendingBarChart Data from transactions
  const spendingChartData = useMemo(() => {
    const daysMap = new Map<string, { amount: number; count: number }>();
    const today = new Date();

    // Prepare last 14 days by default for daily view
    const daysToShow = period === 'day' ? 14 : period === 'week' ? 28 : 60;
    for (let i = daysToShow - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      const key = d.toISOString().split('T')[0];
      daysMap.set(key, { amount: 0, count: 0 });
    }

    // Populate from real transactions
    for (const tx of transactions) {
      if (String(tx.type) === 'expense') {
        const txDate = (tx.transaction_date || tx.date || '').split('T')[0];
        if (daysMap.has(txDate)) {
          const curr = daysMap.get(txDate)!;
          const minor = tx.amount_minor || (tx.amount ? Math.round(tx.amount * 100) : 0);
          curr.amount += minor;
          curr.count += 1;
        }
      }
    }

    // If transactions were empty (fresh workspace), provide informative sample trend
    const hasData = Array.from(daysMap.values()).some((v) => v.amount > 0);
    if (!hasData) {
      // Seed illustrative recent days so the user immediately sees the visual chart
      const sampleAmounts = [145000, 89000, 230000, 45000, 310000, 120000, 67000, 180000, 95000, 240000, 110000, 350000, 160000, 210000];
      let sIdx = 0;
      for (const key of Array.from(daysMap.keys())) {
        daysMap.set(key, {
          amount: sampleAmounts[sIdx % sampleAmounts.length],
          count: (sIdx % 3) + 1,
        });
        sIdx++;
      }
    }

    return Array.from(daysMap.entries()).map(([date, val]) => ({
      date,
      amount_minor: val.amount,
      currency: primaryCurrency,
      count: val.count,
    }));
  }, [transactions, period, primaryCurrency]);

  // Aggregate CategoryPieChart Data
  const categoryChartData = useMemo(() => {
    const catMap = new Map<string, number>();

    for (const tx of transactions) {
      if (String(tx.type) === 'expense') {
        const cat = tx.category || 'Прочее';
        const minor = tx.amount_minor || (tx.amount ? Math.round(tx.amount * 100) : 0);
        catMap.set(cat, (catMap.get(cat) || 0) + minor);
      }
    }

    if (catMap.size === 0) {
      // Seed illustrative breakdown if empty
      return [
        { category: 'Продукты', amount_minor: 3450000, color: getCategoryColor('Продукты') },
        { category: 'Кафе и рестораны', amount_minor: 1850000, color: getCategoryColor('Кафе') },
        { category: 'Транспорт', amount_minor: 1200000, color: getCategoryColor('Транспорт') },
        { category: 'Жилье и ЖКХ', amount_minor: 4500000, color: getCategoryColor('Жилье') },
        { category: 'Подписки', amount_minor: 650000, color: getCategoryColor('Подписки') },
        { category: 'Здоровье', amount_minor: 980000, color: getCategoryColor('Здоровье') },
      ];
    }

    return Array.from(catMap.entries()).map(([category, amount_minor]) => ({
      category,
      amount_minor,
      color: getCategoryColor(category),
    }));
  }, [transactions]);

  // Filtered Transactions for List
  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      const q = txSearch.toLowerCase().trim();
      if (!q) return true;
      const desc = (tx.description || '').toLowerCase();
      const cat = (tx.category || '').toLowerCase();
      const acc = (tx.account_name || '').toLowerCase();
      return desc.includes(q) || cat.includes(q) || acc.includes(q);
    });
  }, [transactions, txSearch]);

  // Handle Quick Expense Submit
  const handleQuickExpenseSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amountVal = parseFloat(expenseAmount.replace(',', '.'));
    if (isNaN(amountVal) || amountVal <= 0) return;

    const accId = selectedAccountId || accounts[0]?.id;
    if (!accId) return;

    const amount_minor = Math.round(amountVal * 100);

    try {
      await createTxMutation.mutateAsync({
        account_id: accId,
        amount_minor,
        currency: primaryCurrency,
        type: TransactionType.EXPENSE,
        description: expenseDescription.trim() || expenseCategory,
        category_id: expenseCategory,
        transaction_date: new Date().toISOString(),
      });

      setExpenseAmount('');
      setExpenseDescription('');
      setFormSuccessMessage('Расход успешно записан!');
      setTimeout(() => setFormSuccessMessage(null), 3000);
    } catch {
      // Handled by query mutation error
    }
  };

  const getAccountIcon = (type: Account['type']) => {
    switch (type) {
      case 'checking':
        return '💳';
      case 'savings':
        return '🏦';
      case 'cash':
        return '💵';
      case 'investment':
        return '📈';
      case 'crypto':
        return '₿';
      default:
        return '💳';
    }
  };

  return (
    <div className="flex flex-col min-h-screen p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Top Header: Title & Total Net Worth */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Финансовый центр
          </h1>
          <p className="text-xs sm:text-sm text-text-secondary mt-0.5">
            Управление счетами, бюджетами категорий и динамика расходов
          </p>
        </div>

        {/* Net Worth Widget */}
        <div className="flex items-center gap-3 bg-surface border border-border px-4 py-3 rounded-2xl shadow-2xs">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-lg font-bold">
            ₽
          </div>
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Общий баланс
            </span>
            <p className="text-lg sm:text-xl font-bold font-mono text-text-primary">
              {formatMinorUnits(totalBalanceMinor, primaryCurrency)}
            </p>
          </div>
        </div>
      </div>

      {/* 1. Account Cards Row */}
      <section aria-label="Финансовые счета" className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Счета и карты ({accounts.length})
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {accountsLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-24 bg-surface-muted animate-pulse rounded-2xl border border-border"
              />
            ))
          ) : accounts.length === 0 ? (
            /* Fallback mock account cards if backend not yet seeded */
            [
              { id: '1', name: 'Основная карта (Т-Банк)', type: 'checking' as const, balance_minor: 14500000, currency: 'RUB' },
              { id: '2', name: 'Накопительный счет', type: 'savings' as const, balance_minor: 48000000, currency: 'RUB' },
              { id: '3', name: 'Наличные в кошельке', type: 'cash' as const, balance_minor: 1250000, currency: 'RUB' },
              { id: '4', name: 'Инвестиционный счет', type: 'investment' as const, balance_minor: 85000000, currency: 'RUB' },
            ].map((acc) => (
              <div
                key={acc.id}
                className="p-4 bg-surface border border-border rounded-2xl shadow-2xs hover:border-primary/40 transition-colors"
              >
                <div className="flex items-center justify-between text-xs text-text-muted mb-2">
                  <span className="flex items-center gap-1.5 font-medium text-text-secondary truncate">
                    <span>{getAccountIcon(acc.type)}</span>
                    <span className="truncate">{acc.name}</span>
                  </span>
                  <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded">
                    {acc.currency}
                  </span>
                </div>
                <p className="text-lg font-bold font-mono text-text-primary tracking-tight">
                  {formatMinorUnits(acc.balance_minor, acc.currency)}
                </p>
              </div>
            ))
          ) : (
            accounts.map((acc) => (
              <div
                key={acc.id}
                className="p-4 bg-surface border border-border rounded-2xl shadow-2xs hover:border-primary/40 transition-colors"
              >
                <div className="flex items-center justify-between text-xs text-text-muted mb-2">
                  <span className="flex items-center gap-1.5 font-medium text-text-secondary truncate">
                    <span>{getAccountIcon(acc.type)}</span>
                    <span className="truncate">{acc.name}</span>
                  </span>
                  <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded">
                    {acc.currency}
                  </span>
                </div>
                <p className="text-lg font-bold font-mono text-text-primary tracking-tight">
                  {formatMinorUnits(acc.balance_minor, acc.currency)}
                </p>
              </div>
            ))
          )}
        </div>
      </section>

      {/* 2. Charts Section: Spending Bar & Category Pie */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7">
          <SpendingBarChart
            data={spendingChartData}
            currency={primaryCurrency}
            period={period}
            onPeriodChange={setPeriod}
          />
        </div>

        <div className="lg:col-span-5">
          <CategoryPieChart
            data={categoryChartData}
            currency={primaryCurrency}
          />
        </div>
      </section>

      {/* 3. Middle Row: Budgets Progress & Quick Expense Form */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Monthly Budgets List */}
        <div className="lg:col-span-7 bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between mb-1">
            <div>
              <h3 className="text-sm font-semibold text-text-primary">
                Бюджеты на текущий месяц
              </h3>
              <p className="text-xs text-text-muted">
                Контроль лимитов с предупреждением о перерасходе
              </p>
            </div>
            <span className="text-xs text-text-muted font-medium">
              {new Date().toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
            </span>
          </div>

          <div className="space-y-2.5">
            {budgetsLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-16 bg-surface-muted animate-pulse rounded-xl" />
              ))
            ) : budgets.length === 0 ? (
              /* Informative demo budget rows */
              [
                {
                  id: 'b1',
                  category_id: 'b1',
                  category_name: 'Продукты и супермаркеты',
                  month: '2026-09',
                  limit_minor: 4000000,
                  current_spent_minor: 2650000,
                  currency: 'RUB',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                {
                  id: 'b2',
                  category_id: 'b2',
                  category_name: 'Кафе и рестораны',
                  month: '2026-09',
                  limit_minor: 2000000,
                  current_spent_minor: 1840000,
                  currency: 'RUB',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                {
                  id: 'b3',
                  category_id: 'b3',
                  category_name: 'Транспорт и такси',
                  month: '2026-09',
                  limit_minor: 1500000,
                  current_spent_minor: 1620000,
                  currency: 'RUB',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                {
                  id: 'b4',
                  category_id: 'b4',
                  category_name: 'Развлечения и кино',
                  month: '2026-09',
                  limit_minor: 1000000,
                  current_spent_minor: 450000,
                  currency: 'RUB',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ].map((b) => (
                <BudgetGaugeRow key={b.id} budget={b} />
              ))
            ) : (
              budgets.map((b) => (
                <BudgetGaugeRow key={b.id} budget={b} />
              ))
            )}
          </div>
        </div>

        {/* Quick Expense Form (Shortcut) */}
        <div className="lg:col-span-5 bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <h3 className="text-sm font-semibold text-text-primary">
                Быстрый ввод расхода
              </h3>
            </div>
            <p className="text-xs text-text-muted mb-4">
              Мгновенное добавление транзакции с пересчётом баланса
            </p>

            <form onSubmit={handleQuickExpenseSubmit} className="space-y-3">
              {/* Account Selector */}
              <div>
                <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                  Счёт списания
                </label>
                <select
                  value={selectedAccountId || (accounts[0]?.id ?? '')}
                  onChange={(e) => setSelectedAccountId(e.target.value)}
                  className="w-full text-xs px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {accounts.length > 0 ? (
                    accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({formatMinorUnits(a.balance_minor, a.currency)})
                      </option>
                    ))
                  ) : (
                    <option value="default">Основная карта (Т-Банк)</option>
                  )}
                </select>
              </div>

              {/* Amount and Category Grid */}
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                    Сумма ({primaryCurrency})
                  </label>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="350.00"
                    required
                    value={expenseAmount}
                    onChange={(e) => setExpenseAmount(e.target.value)}
                    className="w-full text-xs font-mono font-bold px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                    Категория
                  </label>
                  <select
                    value={expenseCategory}
                    onChange={(e) => setExpenseCategory(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="Продукты">🍎 Продукты</option>
                    <option value="Кафе">☕ Кафе и рестораны</option>
                    <option value="Транспорт">🚕 Транспорт / Такси</option>
                    <option value="Жилье">🏠 Жилье и ЖКХ</option>
                    <option value="Подписки">📱 Подписки и софт</option>
                    <option value="Здоровье">💊 Здоровье и аптека</option>
                    <option value="Покупки">🛍️ Одежда и покупки</option>
                    <option value="Развлечения">🎟️ Развлечения</option>
                    <option value="Другое">📦 Другое</option>
                  </select>
                </div>
              </div>

              {/* Description Input */}
              <div>
                <label className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                  Примечание / Описание
                </label>
                <input
                  type="text"
                  placeholder="Например, Обед с коллегами"
                  value={expenseDescription}
                  onChange={(e) => setExpenseDescription(e.target.value)}
                  className="w-full text-xs px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Success Notification */}
              {formSuccessMessage && (
                <div className="p-2 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 rounded-lg text-emerald-700 dark:text-emerald-300 text-xs font-medium text-center animate-fadeIn">
                  ✓ {formSuccessMessage}
                </div>
              )}

              {/* Submit CTA */}
              <button
                type="submit"
                disabled={createTxMutation.isPending || !expenseAmount}
                className="w-full mt-2 py-2.5 px-4 rounded-xl bg-rose-600 hover:bg-rose-700 active:scale-[0.99] disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-2"
              >
                {createTxMutation.isPending ? (
                  <span>Запись транзакции...</span>
                ) : (
                  <>
                    <span>-</span>
                    <span>Записать расход</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* 4. Transactions Ledger with Infinite Scroll */}
      <section className="bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-border">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">
              Журнал операций
            </h3>
            <p className="text-xs text-text-muted">
              История транзакций с фильтрацией и подгрузкой
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Filter by Type */}
            <div className="flex items-center p-0.5 bg-surface-muted rounded-lg border border-border text-[11px]">
              {(['all', 'expense', 'income'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTxTypeFilter(t)}
                  className={cn(
                    'px-2.5 py-1 rounded-md font-medium transition-colors',
                    txTypeFilter === t
                      ? 'bg-surface text-text-primary shadow-2xs font-semibold'
                      : 'text-text-muted hover:text-text-primary'
                  )}
                >
                  {t === 'all' ? 'Все' : t === 'expense' ? 'Расходы' : 'Доходы'}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <input
              type="text"
              placeholder="Поиск по чеку..."
              value={txSearch}
              onChange={(e) => setTxSearch(e.target.value)}
              className="text-xs px-2.5 py-1 bg-surface-muted border border-border rounded-lg text-text-primary focus:outline-none focus:ring-1 focus:ring-primary w-36 sm:w-44"
            />
          </div>
        </div>

        {/* Transactions List Content */}
        <div className="divide-y divide-border/60 max-h-[460px] overflow-y-auto pr-1">
          {txLoading ? (
            <div className="py-8 text-center text-xs text-text-muted">
              Загрузка журнала операций...
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 border border-dashed border-border rounded-xl text-center">
              <p className="text-xs font-semibold text-text-primary">
                Операции не найдены
              </p>
              <p className="text-[11px] text-text-muted mt-0.5">
                Попробуйте изменить параметры фильтра или добавить расход выше
              </p>
            </div>
          ) : (
            filteredTransactions.map((tx) => (
              <ExpenseRow key={tx.id} transaction={tx} />
            ))
          )}

          {/* Infinite Scroll / Load More Trigger */}
          {hasNextPage && (
            <div className="py-3 text-center">
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="px-4 py-1.5 rounded-lg text-xs font-medium bg-surface-muted hover:bg-border text-text-primary transition-colors disabled:opacity-50"
              >
                {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё операции'}
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
