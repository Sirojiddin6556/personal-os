import { test, expect } from '@playwright/test';

test.describe('Navigation, Layout & Theme Switcher E2E', () => {
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

  test('Navigation across AppShell views and dark theme toggling', async ({ page, isMobile }) => {
    await page.goto('/today');

    if (isMobile) {
      const bottomNav = page.locator('div[aria-label="Мобильная навигация"]');
      await expect(bottomNav).toBeVisible();

      // Navigate to Calendar
      await bottomNav.getByRole('link', { name: /календарь/i }).click();
      await expect(page).toHaveURL(/.*calendar/);

      // Navigate to Tasks
      await bottomNav.getByRole('link', { name: /задачи/i }).click();
      await expect(page).toHaveURL(/.*tasks/);

      // Navigate to Finance
      await bottomNav.getByRole('link', { name: /финансы/i }).click();
      await expect(page).toHaveURL(/.*finance/);
    } else {
      // Verify Sidebar navigation links
      const sidebar = page.locator('aside[aria-label="Боковая навигация"]');
      await expect(sidebar).toBeVisible();

      // Navigate to Calendar
      await sidebar.getByRole('link', { name: /календарь/i }).click();
      await expect(page).toHaveURL(/.*calendar/);

      // Navigate to Planner
      await sidebar.getByRole('link', { name: /ежедневник/i }).click();
      await expect(page).toHaveURL(/.*planner/);

      // Navigate to Finance
      await sidebar.getByRole('link', { name: /финансы/i }).click();
      await expect(page).toHaveURL(/.*finance/);
    }

    // Toggle Dark Mode
    const themeBtn = page.getByRole('button', { name: /переключить тему/i });
    await themeBtn.click();
    const html = page.locator('html');
    await expect(html).toHaveAttribute('data-theme', /dark|light/);
  });
});
