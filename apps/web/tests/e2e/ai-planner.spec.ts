import { test, expect } from '@playwright/test';

test.describe('AI Advisor & Morning Brief E2E', () => {
  test('UC-04: Morning Brief view and schedule optimization preview diff', async ({ page }) => {
    await page.goto('/today');

    // Verify Morning Brief Card is displayed
    const briefCard = page.locator('[data-testid="morning-brief-card"]');
    await expect(briefCard).toBeVisible();

    // Check AI suggested schedule blocks
    const aiSuggestionBtn = briefCard.getByRole('button', { name: /предложить расписание/i });
    if (await aiSuggestionBtn.isVisible()) {
      await aiSuggestionBtn.click();
    }

    // Verify AI Preview Diff Dialog appears before applying mutations
    const diffModal = page.getByRole('dialog', { name: /предпросмотр изменений/i });
    await expect(diffModal).toBeVisible();
    await expect(diffModal.getByText(/планируемые перемещения/i)).toBeVisible();

    // Confirm apply
    const applyBtn = diffModal.getByRole('button', { name: /применить всё/i });
    await applyBtn.click();
    await expect(diffModal).not.toBeVisible();

    // Verify schedule updated
    const agendaSection = page.locator('[data-testid="agenda-strip"]');
    await expect(agendaSection).toBeVisible();
  });
});
