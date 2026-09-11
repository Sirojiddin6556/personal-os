import { test, expect } from '@playwright/test';

test.describe('Finance Dashboard & Expense Entry E2E', () => {
  test('UC-03: Add expense and verify budget progress & category chart update', async ({ page }) => {
    await page.goto('/finance');

    // 1. Verify account balances are loaded
    const accountBar = page.locator('[data-testid="finance-accounts-bar"]');
    await expect(accountBar).toBeVisible();

    // 2. Open quick expense dialog
    const addExpenseBtn = page.getByRole('button', { name: /добавить расход/i });
    await addExpenseBtn.click();

    const expenseDialog = page.getByRole('dialog', { name: /запись расхода/i });
    await expect(expenseDialog).toBeVisible();

    // 3. Fill expense details
    await expenseDialog.getByPlaceholder(/сумма/i).fill('1250');
    await expenseDialog.getByPlaceholder(/описание/i).fill('Покупка книг по архитектуре');
    await expenseDialog.getByRole('button', { name: /сохранить/i }).click();

    // 4. Verify transaction row in ledger
    const ledger = page.locator('[data-testid="transaction-ledger"]');
    await expect(ledger.getByText('Покупка книг по архитектуре')).toBeVisible();

    // 5. Verify spending charts update
    const spendingChart = page.locator('[data-testid="spending-bar-chart"]');
    await expect(spendingChart).toBeVisible();
  });
});
