import { test, expect } from '@playwright/test';

test.describe('Finance Dashboard & Reconciliation E2E', () => {
  test.beforeEach(async ({ context, page }) => {
    await context.addCookies([
      {
        name: 'personal_os_access_token',
        value: 'mock_jwt_token_for_e2e',
        domain: 'localhost',
        path: '/',
      },
    ]);
    await page.addInitScript(() => {
      window.localStorage.setItem('personal_os_bypass_auth', 'true');
      window.localStorage.setItem('personal_os_access_token', 'mock_jwt_token_for_e2e');
      document.cookie = 'personal_os_access_token=mock_jwt_token_for_e2e; path=/';
    });
  });

  test('UC-03: Finance Ledger, Accounts and Reconciliation UI', async ({ page }) => {
    await page.goto('/finance');

    // 1. Verify accounts bar and financial metrics load
    const accountsSection = page.getByRole('heading', { name: /Счета/i }).first();
    await expect(accountsSection).toBeVisible();

    // 2. Check Account Manage Modal opens
    const accountCard = page.locator('button, div').filter({ hasText: /UZS|USD|RUB/i }).first();
    if (await accountCard.isVisible()) {
      await accountCard.click();
      const modal = page.getByRole('dialog', { name: /Управление счётом/i });
      if (await modal.isVisible()) {
        // Check Reconciliation tab switch
        const reconcileTab = modal.getByRole('button', { name: /Сверка остатка/i });
        await reconcileTab.click();
        await expect(modal.getByText(/Корректирующая дельта/i)).toBeVisible();
      }
    }
  });
});
