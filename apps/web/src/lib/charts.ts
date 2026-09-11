/**
 * @file charts.ts
 * @description Chart calculation utilities, color mapping, SVG geometric path helpers,
 * and financial minor units formatting for Personal OS dashboards.
 */

import { Priority, PriorityType, TaskStatus, TaskStatusType } from '@/types/domain';

// ============================================================================
// 1. FINANCIAL & NUMBER FORMATTING
// ============================================================================

/**
 * Formats monetary amounts specified in integer minor units (e.g. cents/kopecks).
 * 100 minor units -> "1.00 ₽" (for RUB), "$1.00" (for USD), "€1.00" (for EUR).
 *
 * @param amount Minor unit integer (e.g. 100 for 1.00)
 * @param currency ISO 4217 currency code (default: 'RUB')
 */
export function formatMinorUnits(amount: number, currency: string = 'UZS'): string {
  const isNegative = amount < 0;
  const absVal = Math.abs(amount);
  const major = absVal / 100;
  const curr = (currency || 'UZS').toUpperCase();

  const formattedMajor = major.toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

  const sign = isNegative ? '-' : '';

  switch (curr) {
    case 'UZS':
      return `${sign}${Math.round(major).toLocaleString('ru-RU')} сум`;
    case 'RUB':
      return `${sign}${formattedMajor} ₽`;
    case 'USD':
      return `${sign}$${formattedMajor}`;
    case 'EUR':
      return `${sign}€${formattedMajor}`;
    case 'GBP':
      return `${sign}£${formattedMajor}`;
    case 'JPY':
      return `${sign}¥${formattedMajor}`;
    default:
      return `${sign}${formattedMajor} ${curr}`;
  }
}

/**
 * Calculates and formats ratio percentage.
 * Handles zero total gracefully (returns "0%").
 *
 * @param value Numerator (part)
 * @param total Denominator (whole)
 * @param decimals Number of decimal digits (default: 0)
 */
export function formatPercent(value: number, total: number, decimals: number = 0): string {
  if (!total || total <= 0 || isNaN(value) || isNaN(total)) {
    return '0%';
  }
  const ratio = (value / total) * 100;
  if (decimals === 0) {
    return `${Math.round(ratio)}%`;
  }
  return `${ratio.toFixed(decimals)}%`;
}

/**
 * Compact numeric formatting for chart axes (e.g. 1500 -> "1.5k", 1000000 -> "1M").
 */
export function formatCompactNumber(num: number): string {
  if (Math.abs(num) >= 1_000_000) {
    return (num / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  }
  if (Math.abs(num) >= 1_000) {
    return (num / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  }
  return num.toString();
}

/**
 * Short date formatting for chart X-axes and tooltips.
 */
export function formatChartDate(
  dateStr: string,
  style: 'short' | 'day-only' | 'month-day' | 'full' = 'short'
): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;

    if (style === 'day-only') {
      return d.toLocaleDateString('ru-RU', { weekday: 'short' });
    }
    if (style === 'month-day') {
      return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
    }
    if (style === 'full') {
      return d.toLocaleDateString('ru-RU', {
        weekday: 'short',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      });
    }
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  } catch {
    return dateStr;
  }
}

// ============================================================================
// 2. DOMAIN COLOR MAPPERS
// ============================================================================

/**
 * Predefined palette of accessible, distinct colors for categories.
 */
const CATEGORY_PALETTE: Record<string, string> = {
  // Uzbekistan specific & common categories
  'продукты': '#f59e0b', // amber-500
  'korzinka': '#f59e0b',
  'корзинка': '#f59e0b',
  'makro': '#10b981',
  'макро': '#10b981',
  'еда': '#f59e0b',
  'кафе': '#fb923c',     // orange-400
  'рестораны': '#fb923c',
  'чайхана': '#ea580c',
  'milliy taomlar': '#d97706',
  'evos': '#ef4444',
  'food': '#f59e0b',
  'транспорт': '#0ea5e9', // sky-500
  'такси': '#0284c7',    // sky-600
  'yandex go': '#eab308',
  'яндекс go': '#eab308',
  'яндекс': '#eab308',
  'метро': '#3b82f6',
  'transport': '#0ea5e9',
  'жилье': '#6366f1',    // indigo-500
  'аренда': '#4f46e5',   // indigo-600
  'коммуналка': '#818cf8',
  'коммунальные услуги': '#818cf8',
  'housing': '#6366f1',
  'развлечения': '#ec4899', // pink-500
  'досуг': '#ec4899',
  'кино': '#ec4899',
  'entertainment': '#ec4899',
  'здоровье': '#10b981', // emerald-500
  'аптека': '#059669',   // emerald-600
  'oxymed': '#059669',
  'спорт': '#14b8a6',    // teal-500
  'health': '#10b981',
  'образование': '#8b5cf6', // violet-500
  'книги': '#a855f7',    // purple-500
  'education': '#8b5cf6',
  'покупки': '#f97316',  // orange-500
  'uzum market': '#7c3aed',
  'uzum': '#7c3aed',
  'узум': '#7c3aed',
  'одежда': '#ea580c',
  'shopping': '#f97316',
  'подписки': '#06b6d4', // cyan-500
  'сервисы': '#0891b2',
  'payme': '#00bcd4',
  'click': '#0284c7',
  'связь': '#06b6d4',
  'ucell': '#9333ea',
  'beeline': '#eab308',
  'mobiuz': '#dc2626',
  'subscriptions': '#06b6d4',
  'техника': '#3b82f6',  // blue-500
  'зарплата': '#22c55e', // green-500
  'доход': '#22c55e',
  'гонорар': '#10b981',
  'инвестиции': '#10b981', // emerald-500
  'капиталбанк': '#2563eb',
  'анорбанк': '#ec4899',
  'uzcard': '#3b82f6',
  'humo': '#f97316',
  'другое': '#64748b',   // slate-500
  'other': '#64748b',
};

const DYNAMIC_PALETTE = [
  '#6366f1', // Indigo
  '#0ea5e9', // Sky
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#f97316', // Orange
  '#06b6d4', // Cyan
  '#14b8a6', // Teal
  '#3b82f6', // Blue
  '#a855f7', // Purple
  '#84cc16', // Lime
];

/**
 * Returns a consistent hex color for a category name.
 * Uses exact keyword matching or falls back to a deterministic string hash.
 */
export function getCategoryColor(category: string): string {
  if (!category) return '#64748b';
  const normalized = category.trim().toLowerCase();

  if (CATEGORY_PALETTE[normalized]) {
    return CATEGORY_PALETTE[normalized];
  }

  // Hash code for custom categories
  let hash = 0;
  for (let i = 0; i < normalized.length; i++) {
    hash = (hash << 5) - hash + normalized.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % DYNAMIC_PALETTE.length;
  return DYNAMIC_PALETTE[index];
}

/**
 * Returns hex color matching design tokens for task priority.
 * Aligned with CSS vars in globals.css (--color-priority-*).
 */
export function getPriorityColor(priority: Priority | PriorityType | string): string {
  const norm = String(priority).toLowerCase();
  switch (norm) {
    case 'p1':
    case 'critical':
      return '#dc2626'; // Red-600 (--color-priority-critical)
    case 'p2':
    case 'urgent':
    case 'high':
      return '#f97316'; // Orange-500 (--color-priority-high)
    case 'p3':
    case 'medium':
      return '#eab308'; // Yellow-500 (--color-priority-medium)
    case 'p4':
    case 'low':
    default:
      return '#6b7280'; // Gray-500 (--color-priority-low)
  }
}

/**
 * Returns semantic hex color matching Kanban state machine.
 */
export function getStatusColor(status: TaskStatus | TaskStatusType | string): string {
  const norm = String(status).toLowerCase();
  switch (norm) {
    case 'inbox':
      return '#94a3b8'; // slate-400
    case 'todo':
      return '#64748b'; // slate-500
    case 'backlog':
      return '#6b7280'; // gray-500
    case 'scheduled':
      return '#0ea5e9'; // sky-500
    case 'in_progress':
      return '#6366f1'; // indigo-500
    case 'waiting':
      return '#f59e0b'; // amber-500
    case 'blocked':
      return '#ef4444'; // red-500
    case 'done':
      return '#10b981'; // emerald-500
    case 'canceled':
      return '#9ca3af'; // gray-400
    default:
      return '#64748b';
  }
}

// ============================================================================
// 3. SVG GEOMETRY & PATH BUILDERS
// ============================================================================

export interface Point {
  x: number;
  y: number;
}

/**
 * Generates an SVG cubic bezier path string through a series of points for smooth curves.
 */
export function generateSmoothBezierPath(points: Point[]): string {
  if (!points || points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x},${points[0].y}`;
  if (points.length === 2) {
    return `M ${points[0].x},${points[0].y} L ${points[1].x},${points[1].y}`;
  }

  let d = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = i > 0 ? points[i - 1] : points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = i !== points.length - 2 ? points[i + 2] : p2;

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;

    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    d += ` C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }

  return d;
}

/**
 * Creates a closed SVG path for an area chart with gradient fill under the curve.
 */
export function generateAreaClosedPath(points: Point[], baseY: number): string {
  if (!points || points.length === 0) return '';
  const curve = generateSmoothBezierPath(points);
  const first = points[0];
  const last = points[points.length - 1];

  return `${curve} L ${last.x.toFixed(1)},${baseY.toFixed(1)} L ${first.x.toFixed(1)},${baseY.toFixed(1)} Z`;
}

export interface PieSliceData {
  label: string;
  value: number;
  color: string;
  percentage: number;
  startAngle: number;
  endAngle: number;
  pathD: string;
  midAngle: number;
}

/**
 * Calculates SVG arc paths for donut / pie slices.
 *
 * @param items Array of entries with value and label
 * @param cx Center X
 * @param cy Center Y
 * @param radius Outer radius
 * @param innerRadius Inner radius (0 for solid pie, >0 for donut)
 */
export function calculatePieSlices(
  items: { label: string; value: number; color?: string }[],
  cx: number = 100,
  cy: number = 100,
  radius: number = 80,
  innerRadius: number = 50
): PieSliceData[] {
  const total = items.reduce((acc, curr) => acc + Math.max(0, curr.value), 0);
  if (total <= 0) return [];

  let currentAngle = -Math.PI / 2; // Start at top (12 o'clock)
  const slices: PieSliceData[] = [];

  for (const item of items) {
    const val = Math.max(0, item.value);
    if (val === 0) continue;

    const sliceAngle = (val / total) * 2 * Math.PI;
    const startAngle = currentAngle;
    const endAngle = currentAngle + sliceAngle;
    const midAngle = startAngle + sliceAngle / 2;

    // Outer arc points
    const x1 = cx + radius * Math.cos(startAngle);
    const y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle);
    const y2 = cy + radius * Math.sin(endAngle);

    // Inner arc points
    const x3 = cx + innerRadius * Math.cos(endAngle);
    const y3 = cy + innerRadius * Math.sin(endAngle);
    const x4 = cx + innerRadius * Math.cos(startAngle);
    const y4 = cy + innerRadius * Math.sin(startAngle);

    const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;

    let pathD = '';
    if (innerRadius > 0) {
      pathD = [
        `M ${x1.toFixed(2)} ${y1.toFixed(2)}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
        `L ${x3.toFixed(2)} ${y3.toFixed(2)}`,
        `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x4.toFixed(2)} ${y4.toFixed(2)}`,
        'Z',
      ].join(' ');
    } else {
      pathD = [
        `M ${cx} ${cy}`,
        `L ${x1.toFixed(2)} ${y1.toFixed(2)}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
        'Z',
      ].join(' ');
    }

    slices.push({
      label: item.label,
      value: val,
      color: item.color || getCategoryColor(item.label),
      percentage: (val / total) * 100,
      startAngle,
      endAngle,
      midAngle,
      pathD,
    });

    currentAngle = endAngle;
  }

  return slices;
}
