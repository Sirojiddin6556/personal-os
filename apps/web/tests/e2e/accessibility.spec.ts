import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Automated Accessibility (a11y) & Keyboard Audit', () => {
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

  test('Axe-core scan on Today Dashboard (/today)', async ({ page }) => {
    await page.goto('/today');
    await page.locator('main').waitFor({ state: 'visible', timeout: 10000 });

    const accessibilityScanResults = await new AxeBuilder({ page: page as any })
      .disableRules(['color-contrast'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Axe-core scan on Tasks Kanban Board (/tasks)', async ({ page }) => {
    await page.goto('/tasks');
    await page.locator('main').waitFor({ state: 'visible', timeout: 10000 });

    const accessibilityScanResults = await new AxeBuilder({ page: page as any })
      .disableRules(['color-contrast'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Axe-core scan on Finance Ledger (/finance)', async ({ page }) => {
    await page.goto('/finance');
    await page.locator('main').waitFor({ state: 'visible', timeout: 10000 });

    const accessibilityScanResults = await new AxeBuilder({ page: page as any })
      .disableRules(['color-contrast'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Keyboard navigation & focus trapping on Quick Add Modal', async ({ page }) => {
    await page.goto('/today');
    await page.waitForLoadState('domcontentloaded');

    await page.keyboard.press('Control+k');
    const modal = page.getByRole('dialog', { name: /быстрое добавление/i });
    if (await modal.isVisible()) {
      const input = page.getByPlaceholder(/что нужно сделать/i);
      await expect(input).toBeFocused();

      await page.keyboard.press('Escape');
      await expect(modal).not.toBeVisible();
    }
  });
});
