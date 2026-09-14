import { test, expect } from '@playwright/test';

test.describe('AI Advisor & Morning Brief E2E', () => {
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

  test('UC-04: Today Dashboard schedule and planner view', async ({ page }) => {
    await page.goto('/today');

    // Verify Today Dashboard core sections
    const topTasksSection = page.getByRole('heading', { name: /Топ-3 задачи дня/i });
    await expect(topTasksSection).toBeVisible();

    const agendaSection = page.getByRole('heading', { name: /Расписание и встречи/i });
    await expect(agendaSection).toBeVisible();

    // Navigate to Planner from Today
    await page.getByRole('link', { name: /Ежедневник/i }).first().click();
    await expect(page).toHaveURL(/.*planner/);
  });
});
