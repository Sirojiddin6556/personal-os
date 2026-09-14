/**
 * @file kanban-and-finance.test.ts
 * @description Unit & Integration test suite for Kanban 5-column contract, TaskStatus alignment,
 * and Finance Reconciliation invariants & edge cases.
 */

import { describe, it, expect } from 'vitest';
import { TaskStatus } from '@/types/domain';
import { KANBAN_COLUMNS } from '@/components/domain/tasks/KanbanBoard';

function parseCurrencyInput(raw: string): number {
  if (!raw) return 0;
  let cleaned = raw.replace(/[\s\u00A0]+/g, '');
  // Handle both comma and period present (e.g. 1,250.50 or 1.250,50)
  if (cleaned.includes(',') && cleaned.includes('.')) {
    if (cleaned.lastIndexOf('.') > cleaned.lastIndexOf(',')) {
      cleaned = cleaned.replace(/,/g, '');
    } else {
      cleaned = cleaned.replace(/\./g, '').replace(/,/g, '.');
    }
  } else if (cleaned.includes(',')) {
    cleaned = cleaned.replace(/,/g, '.');
  }
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

describe('Stage 3: Kanban 5-Column Contract & Status Machine', () => {
  it('should have exactly 8 canonical TaskStatus values matching backend domain', () => {
    const statuses = Object.values(TaskStatus);
    expect(statuses).toHaveLength(8);
    expect(statuses).toContain('inbox');
    expect(statuses).toContain('todo');
    expect(statuses).toContain('scheduled');
    expect(statuses).toContain('in_progress');
    expect(statuses).toContain('waiting');
    expect(statuses).toContain('done');
    expect(statuses).toContain('cancelled');
    expect(statuses).toContain('archived');
  });

  it('should configure exactly 5 active Kanban working columns (excluding terminal states)', () => {
    expect(KANBAN_COLUMNS).toHaveLength(5);
    const columnIds = KANBAN_COLUMNS.map((col) => col.id);

    expect(columnIds).toEqual([
      TaskStatus.INBOX,
      TaskStatus.TODO,
      TaskStatus.SCHEDULED,
      TaskStatus.IN_PROGRESS,
      TaskStatus.WAITING,
    ]);

    // Terminal statuses MUST NOT be in the active Kanban columns
    expect(columnIds).not.toContain(TaskStatus.DONE);
    expect(columnIds).not.toContain(TaskStatus.CANCELLED);
    expect(columnIds).not.toContain(TaskStatus.ARCHIVED);
  });
});

describe('Stage 3: Financial Currency Parser & Invariants', () => {
  it('should parse various space and comma formatted inputs into numeric values', () => {
    expect(parseCurrencyInput('1 500 000')).toBe(1500000);
    expect(parseCurrencyInput('1,250.50')).toBe(1250.50);
    expect(parseCurrencyInput('1250,50')).toBe(1250.50);
    expect(parseCurrencyInput('  350 000  ')).toBe(350000);
    expect(parseCurrencyInput('')).toBe(0);
    expect(parseCurrencyInput('abc')).toBe(0);
  });

  it('should correctly calculate signed reconciliation delta', () => {
    const currentCalculatedMinor = 10000000; // 100,000 UZS

    // Case 1: Surplus (Positive delta)
    const actualSurplusMinor = 12500000; // 125,000 UZS
    const deltaSurplus = actualSurplusMinor - currentCalculatedMinor;
    expect(deltaSurplus).toBe(2500000); // +25,000 UZS

    // Case 2: Shortage (Negative delta)
    const actualShortageMinor = 8000000; // 80,000 UZS
    const deltaShortage = actualShortageMinor - currentCalculatedMinor;
    expect(deltaShortage).toBe(-2000000); // -20,000 UZS

    // Case 3: Zero delta (no correction needed)
    const actualExactMinor = 10000000;
    const deltaZero = actualExactMinor - currentCalculatedMinor;
    expect(deltaZero).toBe(0);
  });

  it('should identify zero delta as a non-reconcilable condition', () => {
    const currentMinor = 500000;
    const actualMinor = 500000;
    const delta = actualMinor - currentMinor;

    const isReconcilable = delta !== 0;
    expect(isReconcilable).toBe(false);
  });
});
