const nf = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });

const CURRENCY_LABEL: Record<string, string> = { UZS: 'сум', USD: '$', EUR: '€', RUB: '₽' };

export function money(minor: number, currency = 'UZS'): string {
  return `${nf.format(Math.round(minor / 100))} ${CURRENCY_LABEL[currency] ?? currency}`;
}

export function moneyShort(minor: number): string {
  const v = minor / 100;
  if (Math.abs(v) >= 1_000_000) {
    return `${(Math.round(v / 100_000) / 10).toLocaleString('ru-RU')} млн`;
  }
  if (Math.abs(v) >= 1_000) return `${nf.format(Math.round(v / 1000))} тыс`;
  return nf.format(v);
}

export function time(iso: string): string {
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "Сегодня, 14:00" / "Завтра, 09:00" / "12 нояб." */
export function dueLabel(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return '';
  const d = new Date(iso);
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const hm = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  if (isSameDay(d, now)) return `сегодня, ${hm}`;
  if (isSameDay(d, tomorrow)) return `завтра, ${hm}`;
  if (isSameDay(d, yesterday)) return 'вчера';
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

export function dayTitle(now = new Date()): string {
  const s = now.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return 'Доброй ночи';
  if (h < 12) return 'Доброе утро';
  if (h < 18) return 'Добрый день';
  return 'Добрый вечер';
}

export function hours(n: number): string {
  return `${n.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} ч`;
}

export function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

export function isoDate(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
