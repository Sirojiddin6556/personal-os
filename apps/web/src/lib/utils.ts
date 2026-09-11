import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number, currency: string = 'UZS'): string {
  const curr = (currency || 'UZS').toUpperCase();
  const symbol = curr === 'UZS' ? 'сум' : curr === 'RUB' ? '₽' : curr === 'USD' ? '$' : curr === 'EUR' ? '€' : curr;
  const formattedNumber = Math.abs(amount).toLocaleString('ru-RU');
  return amount < 0 ? `- ${formattedNumber} ${symbol}` : amount > 0 ? `+ ${formattedNumber} ${symbol}` : `0 ${symbol}`;
}

export function formatDateShort(dateString: string): string {
  try {
    const date = new Date(dateString);
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();
    
    const timeStr = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    if (isToday) {
      return `Сегодня, ${timeStr}`;
    }
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateString;
  }
}
