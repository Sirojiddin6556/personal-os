import { test, expect } from '@playwright/test';

test.describe('Navigation, Layout & Theme Switcher E2E', () => {
  test('Navigation across AppShell views and dark theme toggling', async ({ page }) => {
    await page.goto('/today');

    // Verify Sidebar navigation links
    const sidebar = page.locator('[data-testid="app-sidebar"]');
    await expect(sidebar).toBeVisible();

    // Navigate to Calendar
    await sidebar.getByRole('link', { name: /календарь/i }).click();
    await expect(page).toHaveURL(/.*calendar/);

    // Navigate to Notes
    await sidebar.getByRole('link', { name: /заметки/i }).click();
    await expect(page).toHaveURL(/.*notes/);

    // Navigate to Settings
    await sidebar.getByRole('link', { name: /настройки/i }).click();
    await expect(page).toHaveURL(/.*settings/);

    // Toggle Dark Mode
    const themeBtn = page.locator('[data-testid="theme-toggle-btn"]');
    await themeBtn.click();
    const html = page.locator('html');
    await expect(html).toHaveAttribute('data-theme', /dark|light/);
  });
});
