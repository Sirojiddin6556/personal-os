import { describe, expect, it } from 'vitest';
import { parseQuickAdd } from './parse';

const NOW = new Date(2026, 10, 10, 10, 30); // 10 Nov 2026, 10:30 local

describe('parseQuickAdd', () => {
  it('returns null for empty input', () => {
    expect(parseQuickAdd('   ', NOW)).toBeNull();
  });

  it('parses plain amount + category as expense', () => {
    expect(parseQuickAdd('45000 такси', NOW)).toEqual({
      kind: 'expense',
      amountMinor: 4_500_000,
      category: 'Такси',
      currency: 'UZS',
    });
  });

  it('understands "тыс" multiplier and verbs', () => {
    const p = parseQuickAdd('Потратил 120 тыс на обед', NOW);
    expect(p).toMatchObject({ kind: 'expense', amountMinor: 12_000_000, category: 'Обед' });
  });

  it('handles spaces inside numbers and currency', () => {
    expect(parseQuickAdd('1 250 000 сум аренда', NOW)).toMatchObject({ amountMinor: 125_000_000, category: 'Аренда' });
    expect(parseQuickAdd('20$ подписка', NOW)).toMatchObject({ currency: 'USD', amountMinor: 2000 });
  });

  it('does not eat the first letter of a category', () => {
    expect(parseQuickAdd('500 кофе', NOW)).toMatchObject({ amountMinor: 50_000, category: 'Кофе' });
    expect(parseQuickAdd('1500 рынок', NOW)).toMatchObject({ amountMinor: 150_000, category: 'Рынок', currency: 'UZS' });
    expect(parseQuickAdd('30000 вода', NOW)).toMatchObject({ category: 'Вода' });
  });

  it('defaults category', () => {
    expect(parseQuickAdd('5000', NOW)).toMatchObject({ kind: 'expense', category: 'Прочее' });
  });

  it('parses reminder with time later today', () => {
    const p = parseQuickAdd('Напомни позвонить маме в 19:00', NOW);
    expect(p?.kind).toBe('reminder');
    if (p?.kind !== 'reminder') return;
    expect(p.title).toBe('Позвонить маме');
    expect(p.remindAt.getDate()).toBe(10);
    expect(p.remindAt.getHours()).toBe(19);
  });

  it('moves a past reminder time to tomorrow', () => {
    const p = parseQuickAdd('напомни выпить воды в 9:00', NOW);
    if (p?.kind !== 'reminder') throw new Error('expected reminder');
    expect(p.remindAt.getDate()).toBe(11);
  });

  it('parses task with tomorrow', () => {
    const p = parseQuickAdd('Купить молоко завтра', NOW);
    expect(p?.kind).toBe('task');
    if (p?.kind !== 'task') return;
    expect(p.title).toBe('Купить молоко');
    expect(p.dueAt?.getDate()).toBe(11);
    expect(p.priority).toBe('medium');
  });

  it('task with time and urgency', () => {
    const p = parseQuickAdd('срочно отправить отчёт сегодня в 15:00', NOW);
    if (p?.kind !== 'task') throw new Error('expected task');
    expect(p.title).toBe('Отправить отчёт');
    expect(p.priority).toBe('critical');
    expect(p.dueAt?.getHours()).toBe(15);
  });

  it('a leading time is not an amount', () => {
    expect(parseQuickAdd('15:00 созвон с командой', NOW)).toMatchObject({ kind: 'task', title: 'Созвон с командой' });
  });

  it('plain text is an inbox task without due date', () => {
    expect(parseQuickAdd('Идея для блога', NOW)).toEqual({
      kind: 'task',
      title: 'Идея для блога',
      dueAt: null,
      priority: 'medium',
    });
  });
});
