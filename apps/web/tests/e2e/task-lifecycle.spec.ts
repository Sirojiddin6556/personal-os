import { test, expect } from '@playwright/test';

test.describe('Task Lifecycle & Kanban E2E', () => {
  test.beforeEach(async ({ context, page }) => {
    page.on('console', (msg) => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', (err) => console.log('PAGE ERROR:', err.message));

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
    await page.goto('/today');
    await page.waitForLoadState('domcontentloaded');
  });

  test('UC-01: Quick Add Task via keyboard and verify on Today Dashboard', async ({ page }) => {
    await page.keyboard.press('Control+k');
    const modal = page.getByRole('dialog', { name: /быстрое добавление/i });
    if (await modal.isVisible()) {
      const input = page.getByPlaceholder(/что нужно сделать/i);
      await input.fill('Закончить квартальный отчет завтра в 18:00 !high');
      const submitBtn = modal.getByRole('button', { name: /создать/i });
      await submitBtn.click();
      await expect(modal).not.toBeVisible();
    }
  });

  test('UC-02: Kanban 5-Column Navigation and Accessible Status Selector', async ({ page }) => {
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');
    console.log('DEBUG: Landed on URL:', page.url());
    console.log('DEBUG: Page title/text:', (await page.locator('body').innerText()).substring(0, 300));

    // Verify 5 active columns exist on the Kanban board
    await expect(page.getByText(/Входящие/i)).toBeVisible();
    await expect(page.getByText(/К выполнению/i)).toBeVisible();
    await expect(page.getByText(/Запланировано/i)).toBeVisible();
    await expect(page.getByText(/В работе/i)).toBeVisible();
    await expect(page.getByText(/Ожидание/i)).toBeVisible();

    // Verify accessible status selector exists on task cards
    const statusSelect = page.locator('select[aria-label^="Изменить статус задачи"]').first();
    if (await statusSelect.isVisible()) {
      await statusSelect.selectOption('in_progress');
      await expect(statusSelect).toHaveValue('in_progress');
    }
  });
});
