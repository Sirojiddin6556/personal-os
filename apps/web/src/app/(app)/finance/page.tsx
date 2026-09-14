'use client';

import React, { useState, useMemo } from 'react';
import {
  useAccounts,
  useBudgets,
  useCategories,
  useCreateTransaction,
  useTransactions,
} from '@/hooks/useFinance';
import { Account, Transaction, TransactionType } from '@/types/domain';
import { formatMinorUnits, getCategoryColor } from '@/lib/charts';
import { SpendingBarChart } from '@/components/charts/SpendingBarChart';
import { CategoryPieChart } from '@/components/charts/CategoryPieChart';
import { BudgetGaugeRow } from '@/components/charts/BudgetGaugeRow';
import { ExpenseRow } from '@/components/domain/finance/ExpenseRow';
import { AddAccountModal } from '@/components/domain/finance/AddAccountModal';
import { AccountManageModal } from '@/components/domain/finance/AccountManageModal';
import { TransactionDetailModal } from '@/components/domain/finance/TransactionDetailModal';
import { cn } from '@/lib/utils';

export default function FinancePage() {
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('day');
  const [txSearch, setTxSearch] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState<'all' | 'expense' | 'income'>('all');

  // Modals state
  const [isAddAccountOpen, setIsAddAccountOpen] = useState(false);
  const [selectedAccountForManage, setSelectedAccountForManage] = useState<Account | null>(null);
  const [selectedTxForDetail, setSelectedTxForDetail] = useState<Transaction | null>(null);

  // Quick Transaction Form State
  const [formTxType, setFormTxType] = useState<'expense' | 'income'>('expense');
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [expenseAmount, setExpenseAmount] = useState<string>('');
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [expenseDescription, setExpenseDescription] = useState<string>('');
  const [formSuccessMessage, setFormSuccessMessage] = useState<string | null>(null);

  // TanStack Query Hooks
  const { accounts, isLoading: accountsLoading } = useAccounts();
  const { categories } = useCategories();
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

  const displayAccounts = accounts;

  // Primary currency
  const primaryCurrency = displayAccounts[0]?.currency || 'UZS';

  // Total Net Worth across accounts
  const totalBalanceMinor = useMemo(() => {
    return displayAccounts.reduce((acc, a) => {
      if (a.currency && a.currency !== 'UZS') return acc; // Only sum base UZS
      const val = a.balance_minor ?? (a as any).current_balance_minor ?? ((a as any).balance ? Math.round((a as any).balance * 100) : 0);
      return acc + val;
    }, 0);
  }, [displayAccounts]);

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
        const txDate = (tx.occurred_at || tx.transaction_date || tx.date || '').split('T')[0];
        if (daysMap.has(txDate)) {
          const curr = daysMap.get(txDate)!;
          const minor = tx.amount_minor || (tx.amount ? Math.round(tx.amount * 100) : 0);
          curr.amount += minor;
          curr.count += 1;
        }
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

  // Handle Quick Transaction Submit (Expense or Income)
  const handleQuickTransactionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amountVal = parseFloat(expenseAmount.replace(',', '.'));
    if (isNaN(amountVal) || amountVal <= 0) return;

    const accId = selectedAccountId || displayAccounts[0]?.id;
    if (!accId) return;

    const amount_minor = Math.round(amountVal * 100);
    const isIncome = formTxType === 'income';

    // Find category name or use ID
    const cat = categories.find((c) => c.id === selectedCategoryId);
    const catIdOrName = selectedCategoryId || (categories[0]?.id ?? 'Прочие');

    try {
      await createTxMutation.mutateAsync({
        account_id: accId,
        amount_minor,
        currency: primaryCurrency,
        type: isIncome ? TransactionType.INCOME : TransactionType.EXPENSE,
        description: expenseDescription.trim() || (cat ? cat.name : isIncome ? 'Доход' : 'Расход'),
        category_id: catIdOrName,
        transaction_date: new Date().toISOString(),
      });

      setExpenseAmount('');
      setExpenseDescription('');
      setFormSuccessMessage(isIncome ? 'Доход успешно зачислен!' : 'Расход успешно записан!');
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
            Финансовый центр (Узбекистан)
          </h1>
          <p className="text-xs sm:text-sm text-text-secondary mt-0.5">
            Управление счетами Uzcard/Humo, бюджетами в UZS и транзакциями
          </p>
        </div>

        {/* Net Worth Widget */}
        <div className="flex items-center gap-3 bg-surface border border-border px-4 py-3 rounded-2xl shadow-2xs">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-xs font-bold font-mono">
            UZS
          </div>
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Общий баланс
            </span>
            <p className="text-lg sm:text-xl font-bold font-mono text-text-primary">
              {formatMinorUnits(totalBalanceMinor, 'UZS')}
            </p>
          </div>
        </div>
      </div>

      {/* 1. Account Cards Row */}
      <section aria-label="Финансовые счета" className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Счета и карты ({displayAccounts.length})
          </h2>
          <button
            type="button"
            onClick={() => setIsAddAccountOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-primary/10 hover:bg-primary/20 text-primary transition-colors"
          >
            <span>+</span>
            <span>Добавить счёт</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {accountsLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-24 bg-surface-muted animate-pulse rounded-2xl border border-border"
              />
            ))
          ) : displayAccounts.length === 0 ? (
            <div className="col-span-full p-6 bg-surface border border-dashed border-border rounded-2xl text-center space-y-2">
              <p className="text-sm font-semibold text-text-primary">
                Нет добавленных счетов
              </p>
              <p className="text-xs text-text-muted max-w-md mx-auto">
                Создайте ваш первый счёт (Uzcard, Humo, Uzum Bank, наличные или валютную карту), нажав кнопку ниже.
              </p>
              <button
                type="button"
                onClick={() => setIsAddAccountOpen(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-white transition-colors shadow-xs"
              >
                <span>+</span>
                <span>Добавить первый счёт</span>
              </button>
            </div>
          ) : (
            displayAccounts.map((acc) => (
              <div
                key={acc.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedAccountForManage(acc)}
                className="group relative p-4 bg-surface border border-border hover:border-primary/60 rounded-2xl shadow-2xs hover:shadow-sm transition-all cursor-pointer select-none text-left"
              >
                <div className="flex items-center justify-between text-xs text-text-muted mb-2">
                  <span className="flex items-center gap-1.5 font-medium text-text-secondary truncate">
                    <span>{getAccountIcon(acc.type)}</span>
                    <span className="truncate font-semibold text-text-primary group-hover:text-primary transition-colors">
                      {acc.name}
                    </span>
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded">
                      {acc.currency}
                    </span>
                    <span className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity text-xs" title="Управление счётом">
                      ⚙️
                    </span>
                  </div>
                </div>
                <p className="text-lg font-bold font-mono text-text-primary tracking-tight">
                  {formatMinorUnits(acc.balance_minor ?? (acc as any).current_balance_minor ?? ((acc as any).balance ? Math.round((acc as any).balance * 100) : 0), acc.currency)}
                </p>
                <p className="text-[10px] text-text-muted mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  Нажмите для изменения или удаления →
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

      {/* 3. Middle Row: Budgets Progress & Quick Transaction Form */}
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
            ) : !Array.isArray(budgets) || budgets.length === 0 ? (
              <div className="py-8 text-center text-xs text-text-muted border border-dashed border-border rounded-xl">
                Бюджеты на текущий месяц пока не установлены
              </div>
            ) : (
              budgets.map((b) => (
                <BudgetGaugeRow key={b.id} budget={b} />
              ))
            )}
          </div>
        </div>

        {/* Quick Transaction Form (Expense / Income) */}
        <div className="lg:col-span-5 bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className={cn('w-2.5 h-2.5 rounded-full', formTxType === 'expense' ? 'bg-rose-500' : 'bg-emerald-500')} />
                <h3 className="text-sm font-semibold text-text-primary">
                  Быстрая операция
                </h3>
              </div>

              {/* Type Switcher */}
              <div className="flex items-center p-0.5 bg-surface-muted rounded-lg border border-border text-xs">
                <button
                  type="button"
                  onClick={() => setFormTxType('expense')}
                  className={cn(
                    'px-2.5 py-1 rounded-md font-medium transition-colors',
                    formTxType === 'expense'
                      ? 'bg-rose-600 text-white font-semibold shadow-xs'
                      : 'text-text-muted hover:text-text-primary'
                  )}
                >
                  - Расход
                </button>
                <button
                  type="button"
                  onClick={() => setFormTxType('income')}
                  className={cn(
                    'px-2.5 py-1 rounded-md font-medium transition-colors',
                    formTxType === 'income'
                      ? 'bg-emerald-600 text-white font-semibold shadow-xs'
                      : 'text-text-muted hover:text-text-primary'
                  )}
                >
                  + Доход
                </button>
              </div>
            </div>

            <p className="text-xs text-text-muted mb-3.5">
              {formTxType === 'expense'
                ? 'Мгновенное списание средств с пересчётом баланса счёта'
                : 'Зачисление дохода (зарплата, перевод, дивиденды) на счёт'}
            </p>

            <form onSubmit={handleQuickTransactionSubmit} className="space-y-3">
              {/* Account Selector */}
              <div>
                <label htmlFor="quick-tx-account" className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                  {formTxType === 'expense' ? 'Счёт списания' : 'Счёт зачисления'}
                </label>
                <select
                  id="quick-tx-account"
                  aria-label={formTxType === 'expense' ? 'Счёт списания' : 'Счёт зачисления'}
                  value={selectedAccountId || (displayAccounts[0]?.id ?? '')}
                  onChange={(e) => setSelectedAccountId(e.target.value)}
                  disabled={displayAccounts.length === 0}
                  className="w-full text-xs px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60"
                >
                  {displayAccounts.length === 0 ? (
                    <option value="">(Счета не найдены — добавьте счёт)</option>
                  ) : (
                    displayAccounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({formatMinorUnits(a.balance_minor ?? (a as any).current_balance_minor ?? ((a as any).balance ? Math.round((a as any).balance * 100) : 0), a.currency)})
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Amount and Category Grid */}
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label htmlFor="quick-tx-amount" className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                    Сумма ({primaryCurrency})
                  </label>
                  <input
                    id="quick-tx-amount"
                    aria-label={`Сумма в ${primaryCurrency}`}
                    type="text"
                    inputMode="decimal"
                    placeholder="45000"
                    required
                    value={expenseAmount}
                    onChange={(e) => setExpenseAmount(e.target.value)}
                    className="w-full text-xs font-mono font-bold px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <div>
                  <label htmlFor="quick-tx-category" className="block text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-1">
                    Категория
                  </label>
                  <select
                    id="quick-tx-category"
                    aria-label="Категория транзакции"
                    value={selectedCategoryId}
                    onChange={(e) => setSelectedCategoryId(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {categories.length > 0 ? (
                      categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.icon ? `${c.icon} ` : ''}{c.name}
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="Продукты (Korzinka / Makro)">🛒 Продукты (Korzinka / Makro)</option>
                        <option value="Кафе, рестораны и Чайхана">☕ Кафе, рестораны и Чайхана</option>
                        <option value="Транспорт и Yandex Go">🚕 Транспорт и Yandex Go</option>
                        <option value="Связь и Payme/Click">📱 Связь и Payme / Click</option>
                        <option value="Одежда и Uzum Market">🛍️ Одежда и Uzum Market</option>
                        <option value="Жилье и коммуналка">🏠 Жилье и коммуналка</option>
                        <option value="Здоровье и аптека">💊 Здоровье и аптека</option>
                        <option value="Зарплата и доходы">💰 Зарплата и доходы</option>
                        <option value="Другое">📦 Другое</option>
                      </>
                    )}
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
                  placeholder={formTxType === 'expense' ? 'Например: Обед в Milliy Taomlar' : 'Например: Зарплата за сентябрь'}
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
                className={cn(
                  'w-full mt-2 py-2.5 px-4 rounded-xl text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-2 disabled:opacity-50 active:scale-[0.99]',
                  formTxType === 'expense' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-emerald-600 hover:bg-emerald-700'
                )}
              >
                {createTxMutation.isPending ? (
                  <span>Запись транзакции...</span>
                ) : (
                  <>
                    <span>{formTxType === 'expense' ? '-' : '+'}</span>
                    <span>{formTxType === 'expense' ? 'Записать расход' : 'Зачислить доход'}</span>
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
              История транзакций с фильтрацией (нажмите на строку для отмены/деталей)
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
                Попробуйте изменить параметры фильтра или добавить операцию выше
              </p>
            </div>
          ) : (
            filteredTransactions.map((tx) => (
              <ExpenseRow
                key={tx.id}
                transaction={tx}
                onClick={() => setSelectedTxForDetail(tx)}
              />
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

      {/* Add Account Modal */}
      <AddAccountModal
        isOpen={isAddAccountOpen}
        onClose={() => setIsAddAccountOpen(false)}
      />

      {/* Account Manage & Edit Modal */}
      <AccountManageModal
        account={selectedAccountForManage}
        isOpen={!!selectedAccountForManage}
        onClose={() => setSelectedAccountForManage(null)}
      />

      {/* Transaction Detail & Reversal Modal */}
      <TransactionDetailModal
        transaction={selectedTxForDetail}
        isOpen={!!selectedTxForDetail}
        onClose={() => setSelectedTxForDetail(null)}
      />
    </div>
  );
}
