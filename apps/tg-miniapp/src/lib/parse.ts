/**
 * Quick-add parser — same phrases the Telegram bot understands, but runs on the
 * client so the preview is instant and works without an LLM key.
 *
 *   "45000 такси"                    -> expense 45 000 UZS, category "Такси"
 *   "потратил 120 тыс на обед"       -> expense 120 000 UZS, "Обед"
 *   "напомни позвонить маме в 19:00" -> reminder today 19:00
 *   "купить молоко завтра"           -> task due tomorrow
 */
import type { Priority } from './types';

export type Parsed =
  | { kind: 'expense'; amountMinor: number; category: string; currency: 'UZS' | 'USD' | 'EUR' | 'RUB' }
  | { kind: 'reminder'; title: string; remindAt: Date }
  | { kind: 'task'; title: string; dueAt: Date | null; priority: Priority };

const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

const EXPENSE_RE =
  /^(?:расход|потратил[аи]?|потрачено|купил[аи]?|чек|spent)?\s*:?\s*(\d[\d\s]*(?:[.,]\d+)?)\s*(?:(тыс\.?|к|k|млн)(?=\s|$|[$€₽]))?\s*(?:(сум[а-я]*|uzs|\$|usd|долл[а-я]*|€|eur|евро|₽|руб[а-я]*|р\.?)(?=\s|$))?\s*(?:(?:на|в|за)(?=\s|$))?\s*(.*)$/i;

function currencyOf(token: string | undefined): 'UZS' | 'USD' | 'EUR' | 'RUB' {
  const t = (token ?? '').toLowerCase();
  if (t === '$' || t === 'usd' || t.startsWith('долл')) return 'USD';
  if (t === '€' || t === 'eur' || t === 'евро') return 'EUR';
  if (t === '₽' || t.startsWith('руб') || t.startsWith('р')) return 'RUB';
  return 'UZS';
}

function extractTime(low: string): { h: number; m: number } | null {
  const tm = low.match(/(?:^|\s)(?:в|на|к)\s+(\d{1,2})[:.](\d{2})\b/) ?? low.match(/\b(\d{1,2}):(\d{2})\b/);
  if (!tm) return null;
  const h = Number(tm[1]);
  const m = Number(tm[2]);
  if (h > 23 || m > 59) return null;
  return { h, m };
}

function stripTime(s: string): string {
  return s
    .replace(/\s*(?:в|на|к)\s+\d{1,2}[:.]\d{2}\b/gi, ' ')
    .replace(/\s*\b\d{1,2}:\d{2}\b/g, ' ');
}

function dayOffset(low: string): number | null {
  if (/послезавтра/.test(low)) return 2;
  if (/завтра/.test(low)) return 1;
  if (/сегодня/.test(low)) return 0;
  return null;
}

function stripDay(s: string): string {
  return s.replace(/(^|\s)(послезавтра|завтра|сегодня)(?=\s|$)/gi, ' ');
}

export function parseQuickAdd(input: string, now: Date = new Date()): Parsed | null {
  const text = input.trim().replace(/\s+/g, ' ');
  if (!text) return null;
  const low = text.toLowerCase();

  // 1. Expense: starts with an amount (optionally after a verb)
  const m = text.match(EXPENSE_RE);
  if (m && !/^напомн/i.test(low) && !/^\d{1,2}:\d{2}/.test(text)) {
    let amount = parseFloat(m[1].replace(/\s/g, '').replace(',', '.'));
    const mult = (m[2] ?? '').toLowerCase();
    if (mult.startsWith('тыс') || mult === 'к' || mult === 'k') amount *= 1_000;
    if (mult === 'млн') amount *= 1_000_000;
    if (amount > 0 && Number.isFinite(amount)) {
      const category = cap(m[4].trim()) || 'Прочее';
      return { kind: 'expense', amountMinor: Math.round(amount * 100), category, currency: currencyOf(m[3]) };
    }
  }

  const offset = dayOffset(low);
  const t = extractTime(low);

  // 2. Reminder
  if (/^напомн/.test(low)) {
    const at = new Date(now);
    at.setSeconds(0, 0);
    if (offset !== null) at.setDate(now.getDate() + offset);
    if (t) {
      at.setHours(t.h, t.m);
      if (offset === null && at <= now) at.setDate(at.getDate() + 1);
    } else if (offset !== null && offset > 0) {
      at.setHours(9, 0);
    } else {
      at.setTime(now.getTime() + 60 * 60 * 1000);
    }
    const title = cap(
      stripDay(stripTime(text.replace(/^напомн\S*\s*(мне\s*)?/i, '')))
        .replace(/\s+/g, ' ')
        .trim(),
    );
    return { kind: 'reminder', title: title || 'Напоминание', remindAt: at };
  }

  // 3. Task (default)
  let dueAt: Date | null = null;
  if (offset !== null || t) {
    dueAt = new Date(now);
    dueAt.setSeconds(0, 0);
    dueAt.setDate(now.getDate() + (offset ?? 0));
    if (t) dueAt.setHours(t.h, t.m);
    else dueAt.setHours(18, 0);
  }
  const priority: Priority = /срочно|!!|asap/i.test(low) ? 'critical' : /важно|!/.test(low) ? 'high' : 'medium';
  const title = cap(
    stripDay(stripTime(text))
      .replace(/(^|\s)(срочно|важно|asap)(?=\s|$)/gi, ' ').replace(/!+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim(),
  );
  return { kind: 'task', title: title || text, dueAt, priority };
}

/** Map a free-text expense category to a typical category name. */
export function guessCategory(raw: string): string {
  const n = raw.toLowerCase();
  if (/такси|метро|бензин|автобус|транспорт|yandex|uklon/.test(n)) return 'Транспорт';
  if (/кафе|обед|кофе|ресторан|ужин|завтрак/.test(n)) return 'Кафе';
  if (/продукт|еда|магазин|рынок|корзинка|makro/.test(n)) return 'Продукты';
  if (/дом|интернет|свет|газ|аренд|коммунал/.test(n)) return 'Дом';
  return raw;
}
