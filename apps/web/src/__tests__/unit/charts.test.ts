import { describe, it, expect } from 'vitest';
import {
  formatMinorUnits,
  formatPercent,
  formatCompactNumber,
  formatChartDate,
  getCategoryColor,
  getPriorityColor,
  getStatusColor,
  generateSmoothBezierPath,
  generateAreaClosedPath,
  calculatePieSlices,
} from '@/lib/charts';

describe('formatMinorUnits', () => {
  it('formats positive minor units in RUB with Russian locale format', () => {
    const res = formatMinorUnits(10050, 'RUB');
    // In ru-RU locale, 100.50 can have non-breaking space or regular space
    expect(res).toMatch(/100[,.]50\s*₽/);
  });

  it('formats zero minor units in RUB', () => {
    const res = formatMinorUnits(0, 'RUB');
    expect(res).toMatch(/0[,.]00\s*₽/);
  });

  it('formats negative minor units with minus sign', () => {
    const res = formatMinorUnits(-25000, 'RUB');
    expect(res.startsWith('-')).toBe(true);
    expect(res).toMatch(/-250[,.]00\s*₽/);
  });

  it('formats USD with dollar sign prefix', () => {
    expect(formatMinorUnits(100, 'USD')).toBe('$1.00');
    expect(formatMinorUnits(1550, 'USD')).toBe('$15.50');
    expect(formatMinorUnits(-500, 'USD')).toBe('-$5.00');
  });

  it('formats EUR with euro sign prefix', () => {
    expect(formatMinorUnits(2000, 'EUR')).toBe('€20.00');
    expect(formatMinorUnits(-1234, 'EUR')).toBe('-€12.34');
  });

  it('formats GBP with pound sign prefix', () => {
    expect(formatMinorUnits(999, 'GBP')).toBe('£9.99');
    expect(formatMinorUnits(-999, 'GBP')).toBe('-£9.99');
  });

  it('formats JPY with yen sign prefix', () => {
    expect(formatMinorUnits(50000, 'JPY')).toBe('¥500.00');
    expect(formatMinorUnits(-50000, 'JPY')).toBe('-¥500.00');
  });

  it('formats unknown currencies by appending ISO code', () => {
    expect(formatMinorUnits(10000, 'CAD')).toBe('100.00 CAD');
    expect(formatMinorUnits(-10000, 'CAD')).toBe('-100.00 CAD');
  });

  it('handles default currency as RUB when omitted', () => {
    const res = formatMinorUnits(5000);
    expect(res).toMatch(/50[,.]00\s*₽/);
  });
});

describe('formatPercent', () => {
  it('calculates integer percent rounded by default', () => {
    expect(formatPercent(25, 100)).toBe('25%');
    expect(formatPercent(1, 3)).toBe('33%');
    expect(formatPercent(2, 3)).toBe('67%');
  });

  it('formats with requested decimal places', () => {
    expect(formatPercent(1, 3, 1)).toBe('33.3%');
    expect(formatPercent(1, 3, 2)).toBe('33.33%');
  });

  it('handles zero or negative denominator safely', () => {
    expect(formatPercent(50, 0)).toBe('0%');
    expect(formatPercent(50, -10)).toBe('0%');
    expect(formatPercent(NaN, 100)).toBe('0%');
    expect(formatPercent(10, NaN)).toBe('0%');
  });
});

describe('formatCompactNumber', () => {
  it('returns raw number string for numbers below 1000', () => {
    expect(formatCompactNumber(0)).toBe('0');
    expect(formatCompactNumber(450)).toBe('450');
    expect(formatCompactNumber(999)).toBe('999');
  });

  it('formats thousands with k suffix and removes trailing .0', () => {
    expect(formatCompactNumber(1000)).toBe('1k');
    expect(formatCompactNumber(1500)).toBe('1.5k');
    expect(formatCompactNumber(25400)).toBe('25.4k');
  });

  it('formats millions with M suffix and removes trailing .0', () => {
    expect(formatCompactNumber(1000000)).toBe('1M');
    expect(formatCompactNumber(2500000)).toBe('2.5M');
  });
});

describe('formatChartDate', () => {
  const testIsoDate = '2026-07-15T14:30:00Z';

  it('formats short month-day by default', () => {
    const formatted = formatChartDate(testIsoDate);
    expect(formatted).toBeTruthy();
    expect(formatted).toMatch(/15/);
  });

  it('formats day-only style', () => {
    const formatted = formatChartDate(testIsoDate, 'day-only');
    expect(formatted).toBeTruthy();
  });

  it('formats full style', () => {
    const formatted = formatChartDate(testIsoDate, 'full');
    expect(formatted).toMatch(/2026/);
  });

  it('returns raw string when invalid date provided', () => {
    expect(formatChartDate('invalid-date-string')).toBe('invalid-date-string');
  });
});

describe('getCategoryColor', () => {
  it('matches predefined Russian and English category keywords', () => {
    expect(getCategoryColor('продукты')).toBe('#f59e0b');
    expect(getCategoryColor('food')).toBe('#f59e0b');
    expect(getCategoryColor('такси')).toBe('#0284c7');
    expect(getCategoryColor('транспорт')).toBe('#0ea5e9');
    expect(getCategoryColor('жилье')).toBe('#6366f1');
    expect(getCategoryColor('зарплата')).toBe('#22c55e');
  });

  it('returns deterministic color from dynamic palette for unknown categories', () => {
    const color1 = getCategoryColor('Крипто-активы');
    const color2 = getCategoryColor('Крипто-активы');
    expect(color1).toBe(color2);
    expect(color1.startsWith('#')).toBe(true);
  });

  it('returns slate fallback for empty or whitespace category', () => {
    expect(getCategoryColor('')).toBe('#64748b');
  });
});

describe('getPriorityColor', () => {
  it('maps priorities correctly according to design tokens', () => {
    expect(getPriorityColor('p1')).toBe('#dc2626');
    expect(getPriorityColor('critical')).toBe('#dc2626');
    expect(getPriorityColor('p2')).toBe('#f97316');
    expect(getPriorityColor('high')).toBe('#f97316');
    expect(getPriorityColor('p3')).toBe('#eab308');
    expect(getPriorityColor('medium')).toBe('#eab308');
    expect(getPriorityColor('p4')).toBe('#6b7280');
    expect(getPriorityColor('low')).toBe('#6b7280');
    expect(getPriorityColor('unknown')).toBe('#6b7280');
  });
});

describe('getStatusColor', () => {
  it('maps task statuses to semantic hex colors', () => {
    expect(getStatusColor('inbox')).toBe('#94a3b8');
    expect(getStatusColor('todo')).toBe('#64748b');
    expect(getStatusColor('scheduled')).toBe('#0ea5e9');
    expect(getStatusColor('in_progress')).toBe('#6366f1');
    expect(getStatusColor('waiting')).toBe('#f59e0b');
    expect(getStatusColor('blocked')).toBe('#ef4444');
    expect(getStatusColor('done')).toBe('#10b981');
    expect(getStatusColor('canceled')).toBe('#9ca3af');
    expect(getStatusColor('unknown_status')).toBe('#64748b');
  });
});

describe('SVG path helpers: generateSmoothBezierPath and generateAreaClosedPath', () => {
  it('handles empty or single points in generateSmoothBezierPath', () => {
    expect(generateSmoothBezierPath([])).toBe('');
    expect(generateSmoothBezierPath([{ x: 10, y: 20 }])).toBe('M 10,20');
    expect(generateSmoothBezierPath([{ x: 0, y: 0 }, { x: 10, y: 10 }])).toBe('M 0,0 L 10,10');
  });

  it('generates cubic bezier path for 3 or more points', () => {
    const points = [
      { x: 0, y: 100 },
      { x: 50, y: 50 },
      { x: 100, y: 80 },
      { x: 150, y: 20 },
    ];
    const path = generateSmoothBezierPath(points);
    expect(path.startsWith('M 0.0,100.0')).toBe(true);
    expect(path).toContain(' C ');
  });

  it('generates closed area path for area charts', () => {
    const points = [
      { x: 0, y: 100 },
      { x: 50, y: 50 },
      { x: 100, y: 80 },
    ];
    const area = generateAreaClosedPath(points, 200);
    expect(area.startsWith('M 0.0,100.0')).toBe(true);
    expect(area.endsWith('L 100.0,200.0 L 0.0,200.0 Z')).toBe(true);
  });

  it('returns empty string for empty points in generateAreaClosedPath', () => {
    expect(generateAreaClosedPath([], 200)).toBe('');
  });
});

describe('calculatePieSlices', () => {
  it('returns empty array when items array is empty or total is 0', () => {
    expect(calculatePieSlices([])).toEqual([]);
    expect(calculatePieSlices([{ label: 'empty', value: 0 }])).toEqual([]);
  });

  it('calculates single 100% slice correctly', () => {
    const slices = calculatePieSlices([{ label: 'Еда', value: 100 }]);
    expect(slices.length).toBe(1);
    expect(slices[0].percentage).toBe(100);
    expect(slices[0].label).toBe('Еда');
    expect(slices[0].pathD).toBeTruthy();
  });

  it('calculates multiple slices with percentages summing to 100', () => {
    const items = [
      { label: 'Еда', value: 30 },
      { label: 'Транспорт', value: 20 },
      { label: 'Жилье', value: 50 },
    ];
    const slices = calculatePieSlices(items, 100, 100, 80, 50);
    expect(slices.length).toBe(3);
    const sumPct = slices.reduce((acc, s) => acc + s.percentage, 0);
    expect(Math.round(sumPct)).toBe(100);
    expect(slices[0].percentage).toBe(30);
    expect(slices[1].percentage).toBe(20);
    expect(slices[2].percentage).toBe(50);
  });

  it('supports solid pie chart when innerRadius is 0', () => {
    const slices = calculatePieSlices([{ label: 'Test', value: 50 }], 100, 100, 80, 0);
    expect(slices.length).toBe(1);
    expect(slices[0].pathD.startsWith('M 100 100')).toBe(true);
  });
});
