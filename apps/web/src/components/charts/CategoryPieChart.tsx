'use client';

import React, { useState } from 'react';
import {
  calculatePieSlices,
  formatMinorUnits,
  formatPercent,
  getCategoryColor,
} from '@/lib/charts';
import { cn } from '@/lib/utils';

export interface CategoryPieItem {
  category: string;
  amount_minor: number;
  color?: string;
}

export interface CategoryPieChartProps {
  data: CategoryPieItem[];
  currency?: string;
  title?: string;
  innerRadius?: number;
  className?: string;
}

export function CategoryPieChart({
  data = [],
  currency = 'RUB',
  title = 'Расходы по категориям',
  innerRadius = 55,
  className,
}: CategoryPieChartProps) {
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);

  // Group and sort data descending by amount
  const sortedData = [...data]
    .filter((d) => d.amount_minor > 0)
    .sort((a, b) => b.amount_minor - a.amount_minor);

  const totalAmountMinor = sortedData.reduce((acc, d) => acc + d.amount_minor, 0);

  // Prepare input for slice calculation
  const sliceInput = sortedData.map((d) => ({
    label: d.category,
    value: d.amount_minor,
    color: d.color || getCategoryColor(d.category),
  }));

  const slices = calculatePieSlices(sliceInput, 100, 100, 80, innerRadius);

  const activeSlice =
    hoveredCategory !== null
      ? slices.find((s) => s.label.toLowerCase() === hoveredCategory.toLowerCase())
      : null;

  return (
    <div
      className={cn(
        'flex flex-col bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs transition-colors',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {sortedData.length} {sortedData.length === 1 ? 'категория' : 'категорий'}
          </p>
        </div>
        <span className="text-xs font-bold text-text-primary font-mono bg-surface-muted px-2.5 py-1 rounded-lg border border-border">
          {formatMinorUnits(totalAmountMinor, currency)}
        </span>
      </div>

      {sortedData.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-xs text-text-muted border border-dashed border-border rounded-xl">
          Нет данных по категориям за период
        </div>
      ) : (
        <div className="flex flex-col md:flex-row items-center gap-6">
          {/* Donut Chart SVG with Center Readout */}
          <div className="relative w-48 h-48 sm:w-52 sm:h-52 shrink-0 select-none">
            <svg
              viewBox="0 0 200 200"
              role="img"
              aria-label={`Круговая диаграмма расходов по категориям. Всего: ${formatMinorUnits(totalAmountMinor, currency)}`}
              className="w-full h-full transform -rotate-90 origin-center overflow-visible"
            >
              {slices.map((slice) => {
                const isHovered =
                  hoveredCategory?.toLowerCase() === slice.label.toLowerCase();

                // Compute slight outward explosion transform for active slice
                const offset = isHovered ? 4 : 0;
                const ox = offset * Math.cos(slice.midAngle);
                const oy = offset * Math.sin(slice.midAngle);

                return (
                  <path
                    key={slice.label}
                    d={slice.pathD}
                    fill={slice.color}
                    tabIndex={0}
                    role="button"
                    aria-label={`${slice.label}: ${formatMinorUnits(slice.value, currency)} (${formatPercent(slice.value, totalAmountMinor, 1)})`}
                    style={{
                      transform: isHovered ? `translate(${ox}px, ${oy}px)` : undefined,
                      transition: 'transform 150ms ease, opacity 150ms ease',
                    }}
                    onMouseEnter={() => setHoveredCategory(slice.label)}
                    onMouseLeave={() => setHoveredCategory(null)}
                    onFocus={() => setHoveredCategory(slice.label)}
                    onBlur={() => setHoveredCategory(null)}
                    className={cn(
                      'cursor-pointer outline-none stroke-surface stroke-[1.5]',
                      hoveredCategory && !isHovered ? 'opacity-40' : 'opacity-100'
                    )}
                  />
                );
              })}
            </svg>

            {/* Center Dynamic Readout for Donut */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4">
              {activeSlice ? (
                <>
                  <span className="text-[11px] font-semibold text-text-secondary truncate max-w-[110px]">
                    {activeSlice.label}
                  </span>
                  <span className="text-sm font-bold text-text-primary font-mono mt-0.5">
                    {formatMinorUnits(activeSlice.value, currency)}
                  </span>
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/70 px-1.5 py-0.5 rounded-full mt-1">
                    {formatPercent(activeSlice.value, totalAmountMinor, 1)}
                  </span>
                </>
              ) : (
                <>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">
                    Всего
                  </span>
                  <span className="text-sm font-bold text-text-primary font-mono mt-0.5">
                    {formatMinorUnits(totalAmountMinor, currency)}
                  </span>
                  <span className="text-[10px] text-text-muted mt-0.5">100%</span>
                </>
              )}
            </div>
          </div>

          {/* Interactive Legend List */}
          <div className="flex-1 w-full space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {slices.map((slice) => {
              const isHovered =
                hoveredCategory?.toLowerCase() === slice.label.toLowerCase();

              return (
                <div
                  key={slice.label}
                  role="button"
                  tabIndex={0}
                  onMouseEnter={() => setHoveredCategory(slice.label)}
                  onMouseLeave={() => setHoveredCategory(null)}
                  onFocus={() => setHoveredCategory(slice.label)}
                  onBlur={() => setHoveredCategory(null)}
                  className={cn(
                    'flex items-center justify-between p-2 rounded-xl text-xs transition-colors cursor-pointer outline-none select-none',
                    isHovered
                      ? 'bg-surface-muted ring-1 ring-border shadow-2xs'
                      : 'hover:bg-surface-muted/60'
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className="w-3 h-3 rounded-full shrink-0 shadow-2xs"
                      style={{ backgroundColor: slice.color }}
                    />
                    <span className="font-medium text-text-primary truncate">
                      {slice.label}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-2">
                    <span className="font-mono text-text-secondary font-semibold">
                      {formatMinorUnits(slice.value, currency)}
                    </span>
                    <span className="w-11 text-right text-[11px] font-bold text-text-muted font-mono">
                      {formatPercent(slice.value, totalAmountMinor, 1)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default CategoryPieChart;
