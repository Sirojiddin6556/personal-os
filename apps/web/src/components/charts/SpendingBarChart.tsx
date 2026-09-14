'use client';

import React, { useState, useId } from 'react';
import { formatMinorUnits, formatChartDate, formatCompactNumber } from '@/lib/charts';
import { cn } from '@/lib/utils';

export interface SpendingBarItem {
  date: string;
  amount_minor: number;
  currency?: string;
  count?: number;
}

export interface SpendingBarChartProps {
  data: SpendingBarItem[];
  currency?: string;
  title?: string;
  period?: 'day' | 'week' | 'month';
  onPeriodChange?: (period: 'day' | 'week' | 'month') => void;
  height?: number;
  className?: string;
}

export function SpendingBarChart({
  data = [],
  currency = 'RUB',
  title = 'Динамика расходов',
  period = 'day',
  onPeriodChange,
  height = 240,
  className,
}: SpendingBarChartProps) {
  const chartId = useId();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // SVG canvas dimensions
  const svgWidth = 600;
  const svgHeight = height;
  const padLeft = 65;
  const padBottom = 32;
  const padTop = 16;
  const padRight = 16;

  const innerWidth = svgWidth - padLeft - padRight;
  const innerHeight = svgHeight - padTop - padBottom;

  const totalSpentMinor = data.reduce((acc, d) => acc + Math.max(0, d.amount_minor), 0);
  const maxAmountMinor = Math.max(...data.map((d) => Math.max(0, d.amount_minor)), 100);

  // Round up max for clean grid increments
  const niceMax = Math.ceil(maxAmountMinor / 1000) * 1000 || 1000;
  const gridTicks = [0, 0.33, 0.66, 1];

  const colCount = Math.max(data.length, 1);
  const colWidth = innerWidth / colCount;
  const barWidth = Math.min(32, Math.max(12, colWidth * 0.55));

  const activeItem = hoveredIndex !== null && data[hoveredIndex] ? data[hoveredIndex] : null;

  return (
    <div
      className={cn(
        'flex flex-col bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs transition-colors',
        className
      )}
    >
      {/* Header with Title, Period Switcher, and Quick Total */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Всего: <span className="font-semibold text-text-primary">{formatMinorUnits(totalSpentMinor, currency)}</span>
          </p>
        </div>

        {onPeriodChange && (
          <div
            role="group"
            aria-label="Выбор периода"
            className="flex items-center p-0.5 bg-surface-muted rounded-lg border border-border text-[11px]"
          >
            {(['day', 'week', 'month'] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => onPeriodChange(p)}
                className={cn(
                  'px-2.5 py-1 rounded-md font-medium transition-colors',
                  period === p
                    ? 'bg-surface text-text-primary shadow-2xs font-semibold'
                    : 'text-text-muted hover:text-text-primary'
                )}
              >
                {p === 'day' ? 'По дням' : p === 'week' ? 'По неделям' : 'По месяцам'}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Floating Readout / Tooltip Area */}
      <div className="h-6 flex items-center justify-between text-xs px-1 mb-1">
        {activeItem ? (
          <div className="flex items-center gap-2 font-medium animate-fadeIn">
            <span className="text-text-muted">{formatChartDate(activeItem.date, 'full')}:</span>
            <span className="font-bold text-rose-600 dark:text-rose-400">
              {formatMinorUnits(activeItem.amount_minor, activeItem.currency || currency)}
            </span>
            <span className="text-[11px] text-text-muted bg-surface-muted px-1.5 py-0.5 rounded">
              {activeItem.count ?? 1} опер.
            </span>
          </div>
        ) : (
          <span className="text-[11px] text-text-muted">
            Наведите на столбец для просмотра деталей
          </span>
        )}
      </div>

      {/* SVG Chart Graphic */}
      <div className="relative w-full overflow-hidden select-none">
        {data.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-44 text-xs text-text-muted border border-dashed border-border rounded-xl">
            Нет данных о расходах за выбранный период
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            role="img"
            aria-label={`Диаграмма расходов. Всего: ${formatMinorUnits(totalSpentMinor, currency)}`}
            className="w-full h-auto overflow-visible"
          >
            <defs>
              <linearGradient id={`${chartId}-bar-gradient`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#e11d48" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id={`${chartId}-bar-active`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fb7185" stopOpacity="1" />
                <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.85" />
              </linearGradient>
            </defs>

            {/* Y-Axis Horizontal Grid Lines & Labels */}
            {gridTicks.map((ratio) => {
              const tickVal = niceMax * ratio;
              const y = padTop + innerHeight - ratio * innerHeight;
              return (
                <g key={ratio} className="text-text-muted">
                  <line
                    x1={padLeft}
                    y1={y}
                    x2={svgWidth - padRight}
                    y2={y}
                    stroke="currentColor"
                    strokeOpacity={ratio === 0 ? '0.2' : '0.08'}
                    strokeDasharray={ratio === 0 ? undefined : '3 3'}
                  />
                  <text
                    x={padLeft - 8}
                    y={y + 3.5}
                    textAnchor="end"
                    fill="currentColor"
                    className="text-[10px] font-mono fill-current opacity-70"
                  >
                    {formatCompactNumber(tickVal / 100)} {currency === 'RUB' ? '₽' : currency}
                  </text>
                </g>
              );
            })}

            {/* Data Columns & Bars */}
            {data.map((item, index) => {
              const colCenterX = padLeft + index * colWidth + colWidth / 2;
              const barHeight = Math.max(
                4,
                (Math.max(0, item.amount_minor) / niceMax) * innerHeight
              );
              const barY = padTop + innerHeight - barHeight;
              const barX = colCenterX - barWidth / 2;
              const isHovered = hoveredIndex === index;

              return (
                <g
                  key={item.date || index}
                  aria-label={`${formatChartDate(item.date, 'month-day')}: ${formatMinorUnits(item.amount_minor, item.currency || currency)}, ${item.count ?? 1} операций`}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className="cursor-pointer outline-none group"
                >
                  {/* Hover background column highlight */}
                  <rect
                    x={colCenterX - colWidth / 2 + 1}
                    y={padTop}
                    width={colWidth - 2}
                    height={innerHeight}
                    fill="currentColor"
                    className={cn(
                      'text-primary/5 transition-opacity duration-fast pointer-events-none',
                      isHovered ? 'opacity-100' : 'opacity-0'
                    )}
                    rx="4"
                  />

                  {/* Spending Bar with Top Radius */}
                  <rect
                    x={barX}
                    y={barY}
                    width={barWidth}
                    height={barHeight}
                    rx="4"
                    ry="4"
                    fill={`url(#${chartId}-${isHovered ? 'bar-active' : 'bar-gradient'})`}
                    className={cn(
                      'transition-all duration-fast transform-gpu',
                      isHovered ? 'filter drop-shadow(0 2px 6px rgba(244, 63, 94, 0.4))' : ''
                    )}
                  />

                  {/* X-Axis Date Label (subsampled if many items) */}
                  {(data.length <= 14 || index % Math.ceil(data.length / 7) === 0 || index === data.length - 1) && (
                    <text
                      x={colCenterX}
                      y={svgHeight - 10}
                      textAnchor="middle"
                      fill="currentColor"
                      className={cn(
                        'text-[10px] fill-current transition-colors',
                        isHovered
                          ? 'text-text-primary font-bold'
                          : 'text-text-muted opacity-80'
                      )}
                    >
                      {formatChartDate(item.date, data.length <= 7 ? 'day-only' : 'month-day')}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}

export default SpendingBarChart;
