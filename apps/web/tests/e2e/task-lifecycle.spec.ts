import { test, expect } from '@playwright/test';

test.describe('Task Lifecycle & Quick Add E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to Today Dashboard
    await page.goto('/today');
  });

  test('UC-01: Quick Add Task via Cmd+K and verify on Today Dashboard', async ({ page }) => {
    // 1. Trigger Quick Add shortcut or button
    await page.keyboard.press('Control+k');
    const modal = page.getByRole('dialog', { name: /быстрое добавление/i });
    await expect(modal).toBeVisible();

    // 2. Type natural language prompt
    const input = page.getByPlaceholder(/что нужно сделать/i);
    await input.fill('Закончить квартальный отчет завтра в 18:00 !high');

    // 3. Confirm creation
    const submitBtn = modal.getByRole('button', { name: /добавить задачу/i });
    await submitBtn.click();
    await expect(modal).not.toBeVisible();

    // 4. Verify task appears in task lists
    const taskCard = page.locator('[data-testid="task-card"]').filter({ hasText: 'Закончить квартальный отчет' });
    await expect(taskCard).toBeVisible();
    await expect(taskCard.getByText('high', { exact: false })).toBeVisible();
  });

  test('UC-02: Kanban Drag and Drop transition from Inbox to Done', async ({ page }) => {
    await page.goto('/tasks?view=kanban');
    
    // Find task in Inbox column
    const inboxColumn = page.locator('[data-testid="kanban-column-inbox"]');
    const inProgressColumn = page.locator('[data-testid="kanban-column-in_progress"]');
    const taskCard = inboxColumn.locator('[data-testid="task-card"]').first();
    
    // Drag task to In Progress column
    await taskCard.dragTo(inProgressColumn);
    
    // Verify task is now present in In Progress column
    await expect(inProgressColumn.locator('[data-testid="task-card"]').first()).toBeVisible();

    // Complete task via checkbox
    const completeCheckbox = inProgressColumn.locator('[data-testid="task-complete-btn"]').first();
    await completeCheckbox.click();

    // Verify Toast notification with Undo capability appears
    const toast = page.getByRole('status');
    await expect(toast).toContainText(/задача выполнена/i);
    await expect(toast.getByRole('button', { name: /отменить/i })).toBeVisible();
  });
});
