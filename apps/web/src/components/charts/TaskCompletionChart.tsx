'use client';

import React, { useState, useId, useMemo } from 'react';
import {
  generateSmoothBezierPath,
  generateAreaClosedPath,
  formatChartDate,
  Point,
} from '@/lib/charts';
import { cn } from '@/lib/utils';

export interface TaskCompletionDataPoint {
  date: string;
  completed: number;
  created: number;
}

export interface TaskCompletionChartProps {
  data: TaskCompletionDataPoint[];
  period?: '7d' | '30d' | '90d';
  onPeriodChange?: (period: '7d' | '30d' | '90d') => void;
  title?: string;
  height?: number;
  className?: string;
}

export function TaskCompletionChart({
  data = [],
  period = '30d',
  onPeriodChange,
  title = 'Продуктивность и скорость (Velocity)',
  height = 240,
  className,
}: TaskCompletionChartProps) {
  const chartId = useId();
  const [internalPeriod, setInternalPeriod] = useState<'7d' | '30d' | '90d'>(period);
  const activePeriod = onPeriodChange ? period : internalPeriod;

  const handlePeriodClick = (p: '7d' | '30d' | '90d') => {
    if (onPeriodChange) {
      onPeriodChange(p);
    } else {
      setInternalPeriod(p);
    }
  };

  // Filter or limit data by period count
  const filteredData = useMemo(() => {
    const limit = activePeriod === '7d' ? 7 : activePeriod === '30d' ? 30 : 90;
    return data.slice(-limit);
  }, [data, activePeriod]);

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // SVG coordinate setup
  const svgWidth = 640;
  const svgHeight = height;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 16;
  const padBottom = 32;

  const innerWidth = svgWidth - padLeft - padRight;
  const innerHeight = svgHeight - padTop - padBottom;

  const maxVal = Math.max(
    ...filteredData.map((d) => Math.max(d.completed, d.created)),
    4
  );
  // Nice integer ceiling
  const niceMax = Math.ceil(maxVal);

  // Calculate points
  const { completedPoints, createdPoints } = useMemo(() => {
    const count = filteredData.length;
    if (count === 0) return { completedPoints: [], createdPoints: [] };

    const cPoints: Point[] = [];
    const crPoints: Point[] = [];

    for (let i = 0; i < count; i++) {
      const item = filteredData[i];
      const x = count === 1 ? padLeft + innerWidth / 2 : padLeft + (i / (count - 1)) * innerWidth;
      const yCompleted = padTop + innerHeight - (item.completed / niceMax) * innerHeight;
      const yCreated = padTop + innerHeight - (item.created / niceMax) * innerHeight;

      cPoints.push({ x, y: yCompleted });
      crPoints.push({ x, y: yCreated });
    }

    return { completedPoints: cPoints, createdPoints: crPoints };
  }, [filteredData, innerWidth, innerHeight, niceMax, padLeft, padTop]);

  const completedPath = generateSmoothBezierPath(completedPoints);
  const completedAreaPath = generateAreaClosedPath(
    completedPoints,
    padTop + innerHeight
  );
  const createdPath = generateSmoothBezierPath(createdPoints);

  const totalCompleted = filteredData.reduce((acc, d) => acc + d.completed, 0);
  const totalCreated = filteredData.reduce((acc, d) => acc + d.created, 0);
  const netVelocity = totalCompleted - totalCreated;

  const activePoint =
    hoveredIndex !== null && filteredData[hoveredIndex]
      ? filteredData[hoveredIndex]
      : null;
  const activeCompletedPos =
    hoveredIndex !== null && completedPoints[hoveredIndex]
      ? completedPoints[hoveredIndex]
      : null;
  const activeCreatedPos =
    hoveredIndex !== null && createdPoints[hoveredIndex]
      ? createdPoints[hoveredIndex]
      : null;

  // Grid ticks (0, 33%, 66%, 100%)
  const gridTicks = [0, 0.33, 0.66, 1];

  return (
    <div
      className={cn(
        'flex flex-col bg-surface border border-border rounded-2xl p-4 sm:p-5 shadow-2xs transition-colors',
        className
      )}
    >
      {/* Header Toolbar: Title, Period Buttons, and Summary KPI */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <div className="flex items-center gap-3 text-xs text-text-muted mt-0.5">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              Завершено: <strong className="text-text-primary">{totalCompleted}</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
              Создано: <strong className="text-text-primary">{totalCreated}</strong>
            </span>
            <span className="text-[11px] font-mono font-medium">
              Дельта:{' '}
              <span
                className={cn(
                  'font-bold',
                  netVelocity >= 0
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-rose-600 dark:text-rose-400'
                )}
              >
                {netVelocity >= 0 ? `+${netVelocity}` : netVelocity}
              </span>
            </span>
          </div>
        </div>

        {/* Time Period Selector: 7d / 30d / 90d */}
        <div
          role="tablist"
          aria-label="Временной диапазон"
          className="flex items-center p-0.5 bg-surface-muted rounded-lg border border-border text-[11px]"
        >
          {(['7d', '30d', '90d'] as const).map((p) => (
            <button
              key={p}
              type="button"
              role="tab"
              aria-selected={activePeriod === p}
              onClick={() => handlePeriodClick(p)}
              className={cn(
                'px-2.5 py-1 rounded-md font-medium transition-colors',
                activePeriod === p
                  ? 'bg-surface text-text-primary shadow-2xs font-semibold'
                  : 'text-text-muted hover:text-text-primary'
              )}
            >
              {p === '7d' ? '7 дней' : p === '30d' ? '30 дней' : '90 дней'}
            </button>
          ))}
        </div>
      </div>

      {/* Hover Readout Bar */}
      <div className="h-6 flex items-center justify-between text-xs px-1 mb-1">
        {activePoint ? (
          <div className="flex items-center gap-3 font-medium animate-fadeIn">
            <span className="text-text-muted">
              {formatChartDate(activePoint.date, 'full')}:
            </span>
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">
              ✓ {activePoint.completed} завершено
            </span>
            <span className="text-indigo-600 dark:text-indigo-400 font-bold">
              + {activePoint.created} создано
            </span>
            <span className="text-[11px] text-text-muted">
              Баланс:{' '}
              <strong
                className={
                  activePoint.completed - activePoint.created >= 0
                    ? 'text-emerald-600'
                    : 'text-rose-600'
                }
              >
                {activePoint.completed - activePoint.created >= 0
                  ? `+${activePoint.completed - activePoint.created}`
                  : activePoint.completed - activePoint.created}
              </strong>
            </span>
          </div>
        ) : (
          <span className="text-[11px] text-text-muted">
            Наведите на график для просмотра динамики задач
          </span>
        )}
      </div>

      {/* SVG Canvas Area */}
      <div className="relative w-full overflow-hidden select-none">
        {filteredData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-44 text-xs text-text-muted border border-dashed border-border rounded-xl">
            Нет данных о задачах за указанный период
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            role="img"
            aria-label={`График выполнения задач за ${activePeriod}: завершено ${totalCompleted}, создано ${totalCreated}`}
            onMouseLeave={() => setHoveredIndex(null)}
            className="w-full h-auto overflow-visible cursor-crosshair"
          >
            <defs>
              <linearGradient
                id={`${chartId}-completed-area`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Horizontal Grid Lines and Y-Axis Ticks */}
            {gridTicks.map((ratio) => {
              const tickVal = Math.round(niceMax * ratio);
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
                    x={padLeft - 6}
                    y={y + 3.5}
                    textAnchor="end"
                    fill="currentColor"
                    className="text-[10px] font-mono fill-current opacity-70"
                  >
                    {tickVal}
                  </text>
                </g>
              );
            })}

            {/* Completed Area Gradient Fill */}
            {completedAreaPath && (
              <path
                d={completedAreaPath}
                fill={`url(#${chartId}-completed-area)`}
                className="pointer-events-none"
              />
            )}

            {/* Created Series Line (Dashed Indigo) */}
            {createdPath && (
              <path
                d={createdPath}
                fill="none"
                stroke="#6366f1"
                strokeWidth={2}
                strokeDasharray="4 3"
                strokeOpacity={0.8}
                className="pointer-events-none"
              />
            )}

            {/* Completed Series Line (Solid Emerald) */}
            {completedPath && (
              <path
                d={completedPath}
                fill="none"
                stroke="#10b981"
                strokeWidth={2.5}
                strokeLinecap="round"
                className="pointer-events-none"
              />
            )}

            {/* X-Axis Date Ticks */}
            {filteredData.map((item, idx) => {
              const count = filteredData.length;
              const x =
                count === 1
                  ? padLeft + innerWidth / 2
                  : padLeft + (idx / (count - 1)) * innerWidth;

              // Subsample X labels based on period
              const step = count <= 7 ? 1 : count <= 30 ? 5 : 15;
              const shouldShowLabel = idx % step === 0 || idx === count - 1;

              return (
                <g key={item.date || idx}>
                  {shouldShowLabel && (
                    <text
                      x={x}
                      y={svgHeight - 10}
                      textAnchor="middle"
                      fill="currentColor"
                      className="text-[10px] fill-current text-text-muted opacity-80"
                    >
                      {formatChartDate(item.date, count <= 7 ? 'day-only' : 'month-day')}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Active Vertical Crosshair and Dots */}
            {hoveredIndex !== null && activeCompletedPos && activeCreatedPos && (
              <g className="pointer-events-none">
                <line
                  x1={activeCompletedPos.x}
                  y1={padTop}
                  x2={activeCompletedPos.x}
                  y2={padTop + innerHeight}
                  stroke="currentColor"
                  strokeOpacity={0.3}
                  strokeDasharray="2 2"
                />

                {/* Created Dot */}
                <circle
                  cx={activeCreatedPos.x}
                  cy={activeCreatedPos.y}
                  r={4}
                  fill="#6366f1"
                  stroke="#ffffff"
                  strokeWidth={2}
                />

                {/* Completed Dot */}
                <circle
                  cx={activeCompletedPos.x}
                  cy={activeCompletedPos.y}
                  r={5}
                  fill="#10b981"
                  stroke="#ffffff"
                  strokeWidth={2}
                  className="filter drop-shadow(0 1px 3px rgba(16, 185, 129, 0.6))"
                />
              </g>
            )}

            {/* Invisible Hover Rectangles along X for smooth cursor tracking */}
            {filteredData.map((_item, idx) => {
              const count = filteredData.length;
              const colW = innerWidth / count;
              const x = padLeft + idx * colW;

              return (
                <rect
                  key={idx}
                  x={x}
                  y={padTop}
                  width={colW}
                  height={innerHeight}
                  fill="transparent"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseMove={() => setHoveredIndex(idx)}
                  className="cursor-crosshair"
                />
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}

export default TaskCompletionChart;
