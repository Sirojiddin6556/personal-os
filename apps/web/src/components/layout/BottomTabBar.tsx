'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useUIStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';

export function BottomTabBar() {
  const pathname = usePathname() || '/today';
  const { openQuickAdd } = useUIStore();

  return (
    <div
      role="navigation"
      aria-label="Мобильная навигация"
      className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-surface/95 backdrop-blur-md border-t border-border pb-[env(safe-area-inset-bottom,0px)] shadow-lg"
    >
      <div className="flex items-center justify-around h-16 px-2 relative">
        {/* Tab 1: Today */}
        <a
          href="/today"
          className={cn(
            'flex flex-col items-center justify-center flex-1 py-1 text-xs transition-colors',
            pathname === '/today'
              ? 'text-primary font-bold'
              : 'text-text-muted hover:text-text-primary'
          )}
        >
          <svg className="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          <span>Сегодня</span>
        </a>

        {/* Tab 2: Tasks */}
        <a
          href="/tasks"
          className={cn(
            'flex flex-col items-center justify-center flex-1 py-1 text-xs transition-colors',
            pathname.startsWith('/tasks')
              ? 'text-primary font-bold'
              : 'text-text-muted hover:text-text-primary'
          )}
        >
          <svg className="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
            <path d="M9 16l2 2 4-4" />
          </svg>
          <span>Задачи</span>
        </a>

        {/* Tab 3: Central FAB (Quick Add) */}
        <div className="flex-1 flex justify-center -mt-6">
          <button
            onClick={() => openQuickAdd('task')}
            aria-label="Быстрое добавление"
            className="w-12 h-12 rounded-full bg-primary hover:bg-primary-600 text-white shadow-lg flex items-center justify-center ring-4 ring-background active:scale-95 transition-transform"
          >
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        {/* Tab 4: Calendar */}
        <a
          href="/calendar"
          className={cn(
            'flex flex-col items-center justify-center flex-1 py-1 text-xs transition-colors',
            pathname.startsWith('/calendar')
              ? 'text-primary font-bold'
              : 'text-text-muted hover:text-text-primary'
          )}
        >
          <svg className="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span>Календарь</span>
        </a>

        {/* Tab 5: Finance */}
        <a
          href="/finance"
          className={cn(
            'flex flex-col items-center justify-center flex-1 py-1 text-xs transition-colors',
            pathname.startsWith('/finance')
              ? 'text-primary font-bold'
              : 'text-text-muted hover:text-text-primary'
          )}
        >
          <svg className="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <line x1="2" y1="10" x2="22" y2="10" />
          </svg>
          <span>Финансы</span>
        </a>
      </div>
    </div>
  );
}
