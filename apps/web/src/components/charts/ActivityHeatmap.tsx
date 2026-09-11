'use client';

import React, { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

export interface ActivityDay {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface ActivityHeatmapProps {
  data: ActivityDay[];
  weeksCount?: number;
  title?: string;
  onDayClick?: (day: ActivityDay) => void;
  className?: string;
}

export function ActivityHeatmap({
  data = [],
  weeksCount = 52,
  title = 'История активности',
  onDayClick,
  className,
}: ActivityHeatmapProps) {
  const [hoveredDay, setHoveredDay] = useState<ActivityDay | null>(null);

  // Fast map lookup by YYYY-MM-DD
  const countsMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of data) {
      if (d.date) {
        // Normalize date to YYYY-MM-DD
        const dateKey = d.date.split('T')[0];
        map.set(dateKey, (map.get(dateKey) || 0) + d.count);
      }
    }
    return map;
  }, [data]);

  // Generate 52 weeks of days ending today
  const { weeks, monthLabels, totalActions, activeDaysCount } = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // End on Sunday or current day of this week to align columns
    const dayOfWeek = (today.getDay() + 6) % 7; // Monday = 0, Sunday = 6
    const daysToGenerate = weeksCount * 7 + (6 - dayOfWeek);

    const startDate = new Date(today);
    startDate.setDate(today.getDate() - daysToGenerate + 1);

    const generatedWeeks: Array<Array<{ dateStr: string; dateObj: Date; count: number; isFuture: boolean }>> = [];
    const months: Array<{ monthName: string; weekIndex: number }> = [];

    let currentWeek: Array<{ dateStr: string; dateObj: Date; count: number; isFuture: boolean }> = [];
    let lastMonth = -1;
    let totalCount = 0;
    let activeDays = 0;

    for (let i = 0; i < daysToGenerate; i++) {
      const current = new Date(startDate);
      current.setDate(startDate.getDate() + i);

      const yyyy = current.getFullYear();
      const mm = String(current.getMonth() + 1).padStart(2, '0');
      const dd = String(current.getDate()).padStart(2, '0');
      const dateStr = `${yyyy}-${mm}-${dd}`;

      const isFuture = current > today;
      const count = isFuture ? 0 : countsMap.get(dateStr) || 0;

      if (!isFuture) {
        totalCount += count;
        if (count > 0) activeDays++;
      }

      currentWeek.push({
        dateStr,
        dateObj: current,
        count,
        isFuture,
      });

      // Track month labels at start of new month
      if (current.getDate() <= 7 && current.getMonth() !== lastMonth) {
        lastMonth = current.getMonth();
        const monthName = current.toLocaleDateString('ru-RU', { month: 'short' });
        months.push({
          monthName,
          weekIndex: generatedWeeks.length,
        });
      }

      if (currentWeek.length === 7) {
        generatedWeeks.push(currentWeek);
        currentWeek = [];
      }
    }

    // Keep only requested number of weeks
    const trimmedWeeks = generatedWeeks.slice(-weeksCount);

    return {
      weeks: trimmedWeeks,
      monthLabels: months.filter((m) => m.weekIndex >= generatedWeeks.length - weeksCount),
      totalActions: totalCount,
      activeDaysCount: activeDays,
    };
  }, [countsMap, weeksCount]);

  // Intensity color tiers (Level 0 to Level 4)
  const getIntensityLevel = (count: number, isFuture: boolean): number => {
    if (isFuture) return -1;
    if (count === 0) return 0;
    if (count <= 2) return 1;
    if (count <= 5) return 2;
    if (count <= 8) return 3;
    return 4;
  };

  const getCellFill = (level: number): string => {
    switch (level) {
      case -1:
        return 'fill-transparent';
      case 0:
        return 'fill-surface-muted dark:fill-slate-800/60 stroke-border/40';
      case 1:
        return 'fill-emerald-200 dark:fill-emerald-950 stroke-emerald-300/40 dark:stroke-emerald-800/40';
      case 2:
        return 'fill-emerald-400 dark:fill-emerald-700 stroke-emerald-500/40 dark:stroke-emerald-600/40';
      case 3:
        return 'fill-emerald-600 dark:fill-emerald-500 stroke-emerald-700/40 dark:stroke-emerald-400/40';
      case 4:
        return 'fill-emerald-700 dark:fill-emerald-400 stroke-emerald-800/40 dark:stroke-emerald-300/40';
      default:
        return 'fill-surface-muted';
    }
  };

  // Dimensions
  const cellSize = 11;
  const cellGap = 3;
  const padLeft = 28;
  const padTop = 20;
  const totalSvgWidth = padLeft + weeks.length * (cellSize + cellGap);
  const totalSvgHeight = padTop + 7 * (cellSize + cellGap) + 12;

  const dayLabels = [
    { label: 'Пн', rowIndex: 0 },
    { label: 'Ср', rowIndex: 2 },
    { label: 'Пт', rowIndex: 4 },
  ];

  return (
    <div
      className={cn(
        'flex flex-col bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs transition-colors',
        className
      )}
    >
      {/* Header with Title and Summary Stats */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {totalActions} действий за {weeksCount} недель • {activeDaysCount} продуктивных дней
          </p>
        </div>

        {/* Hover Readout */}
        <div className="h-6 flex items-center text-xs">
          {hoveredDay ? (
            <div className="flex items-center gap-2 bg-surface-muted px-2.5 py-1 rounded-lg border border-border font-medium">
              <span className="text-text-muted">
                {new Date(hoveredDay.date).toLocaleDateString('ru-RU', {
                  weekday: 'short',
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
                :
              </span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">
                {hoveredDay.count > 0 ? `${hoveredDay.count} действий` : 'Нет действий'}
              </span>
            </div>
          ) : (
            <span className="text-[11px] text-text-muted">
              Наведите на день для информации
            </span>
          )}
        </div>
      </div>

      {/* Heatmap SVG Container with Horizontal Scroll */}
      <div className="w-full overflow-x-auto pb-2 select-none">
        <svg
          viewBox={`0 0 ${totalSvgWidth} ${totalSvgHeight}`}
          role="img"
          aria-label={`Тепловая карта активности за ${weeksCount} недель: ${totalActions} действий.`}
          style={{ minWidth: `${Math.min(totalSvgWidth, 720)}px` }}
          className="w-full h-auto overflow-visible"
        >
          {/* Month Labels */}
          {monthLabels.map((m, idx) => {
            const x = padLeft + m.weekIndex * (cellSize + cellGap);
            return (
              <text
                key={`${m.monthName}-${idx}`}
                x={x}
                y={padTop - 8}
                className="text-[10px] fill-current text-text-muted font-medium"
              >
                {m.monthName}
              </text>
            );
          })}

          {/* Day of Week Labels (Mon, Wed, Fri) */}
          {dayLabels.map((d) => {
            const y = padTop + d.rowIndex * (cellSize + cellGap) + cellSize - 2;
            return (
              <text
                key={d.label}
                x={padLeft - 8}
                y={y}
                textAnchor="end"
                className="text-[9px] fill-current text-text-muted font-medium"
              >
                {d.label}
              </text>
            );
          })}

          {/* Weeks & Days Grid Cells */}
          {weeks.map((week, weekIdx) => {
            const colX = padLeft + weekIdx * (cellSize + cellGap);

            return (
              <g key={`week-${weekIdx}`}>
                {week.map((day, dayIdx) => {
                  if (day.isFuture) return null;

                  const rowY = padTop + dayIdx * (cellSize + cellGap);
                  const level = getIntensityLevel(day.count, day.isFuture);
                  const isHovered = hoveredDay?.date === day.dateStr;

                  return (
                    <rect
                      key={day.dateStr}
                      x={colX}
                      y={rowY}
                      width={cellSize}
                      height={cellSize}
                      rx={2.5}
                      ry={2.5}
                      strokeWidth={1}
                      tabIndex={0}
                      role="button"
                      aria-label={`${day.dateStr}: ${day.count} действий`}
                      className={cn(
                        'cursor-pointer transition-all duration-fast outline-none',
                        getCellFill(level),
                        isHovered && 'stroke-primary stroke-2 filter drop-shadow(0 1px 3px rgba(16, 185, 129, 0.5))'
                      )}
                      onMouseEnter={() =>
                        setHoveredDay({ date: day.dateStr, count: day.count })
                      }
                      onMouseLeave={() => setHoveredDay(null)}
                      onFocus={() =>
                        setHoveredDay({ date: day.dateStr, count: day.count })
                      }
                      onBlur={() => setHoveredDay(null)}
                      onClick={() =>
                        onDayClick?.({ date: day.dateStr, count: day.count })
                      }
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend at Bottom Right */}
      <div className="flex items-center justify-between text-xs text-text-muted mt-3 pt-2 border-t border-border/60">
        <span className="text-[11px]">Календарная сетка активности (Пн - Вс)</span>

        <div className="flex items-center gap-1.5 text-[11px]">
          <span>Меньше</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <span
              key={level}
              className={cn(
                'inline-block w-2.5 h-2.5 rounded-xs border',
                level === 0 && 'bg-surface-muted dark:bg-slate-800 border-border',
                level === 1 && 'bg-emerald-200 dark:bg-emerald-950 border-emerald-300 dark:border-emerald-800',
                level === 2 && 'bg-emerald-400 dark:bg-emerald-700 border-emerald-500 dark:border-emerald-600',
                level === 3 && 'bg-emerald-600 dark:bg-emerald-500 border-emerald-700 dark:border-emerald-400',
                level === 4 && 'bg-emerald-700 dark:bg-emerald-400 border-emerald-800 dark:border-emerald-300'
              )}
            />
          ))}
          <span>Больше</span>
        </div>
      </div>
    </div>
  );
}

export default ActivityHeatmap;
