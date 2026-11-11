'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useUIStore } from '@/stores/ui-store';
import { cn, withBase } from '@/lib/utils';

// Sections used every day stay on top; the rest live under "Ещё".
const MAIN = ['/today', '/tasks', '/calendar', '/finance'];

export function SidebarNav() {
  const pathname = usePathname() || '/today';
  const { isSidebarCollapsed, toggleSidebar } = useUIStore();
  const [moreOpen, setMoreOpen] = React.useState(false);

  const allItems = [
    {
      label: 'Сегодня',
      href: '/today',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      ),
    },
    {
      label: 'Ежедневник',
      href: '/planner',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          <line x1="8" y1="7" x2="16" y2="7" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      ),
    },
    {
      label: 'Задачи',
      href: '/tasks',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
          <path d="M9 16l2 2 4-4" />
        </svg>
      ),
    },
    {
      label: 'Заметки',
      href: '/notes',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="8" y1="13" x2="16" y2="13" />
          <line x1="8" y1="17" x2="13" y2="17" />
        </svg>
      ),
    },
    {
      label: 'Проекты и GitHub',
      href: '/projects',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
        </svg>
      ),
    },
    {
      label: 'Календарь',
      href: '/calendar',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      ),
    },
    {
      label: 'Финансы',
      href: '/finance',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="4" width="20" height="16" rx="2" />
          <line x1="2" y1="10" x2="22" y2="10" />
        </svg>
      ),
    },
    {
      label: 'Аналитика',
      href: '/analytics',
      badge: null,
      icon: (
        <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" />
          <path d="M18 9l-5 5-4-4-6 6" />
        </svg>
      ),
    },
  ];
  const navItems = allItems.filter((i) => MAIN.includes(i.href));
  const moreItems = allItems.filter((i) => !MAIN.includes(i.href));
  const moreActive = moreItems.some((i) => pathname.startsWith(i.href));
  const showMore = moreOpen || moreActive || isSidebarCollapsed;

  const renderItem = (item: (typeof allItems)[number]) => {
    const isActive = pathname.startsWith(item.href);
    return (
      <a
        key={item.href}
        href={item.href}
        title={isSidebarCollapsed ? item.label : undefined}
        aria-current={isActive ? 'page' : undefined}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-fast',
          isActive
            ? 'bg-primary/10 text-primary-600 dark:text-primary-400 font-semibold'
            : 'text-text-secondary hover:text-text-primary hover:bg-surface-muted',
          isSidebarCollapsed && 'justify-center px-0'
        )}
      >
        {item.icon}
        {!isSidebarCollapsed && <span className="truncate flex-1">{item.label}</span>}
      </a>
    );
  };

  return (
    <aside
      aria-label="Боковая навигация"
      className={cn(
        'hidden lg:flex flex-col h-screen border-r border-border bg-surface select-none transition-all duration-250 shrink-0 sticky top-0 z-30',
        isSidebarCollapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center px-4 justify-between border-b border-border">
        <a href="/today" className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-primary text-white flex items-center justify-center font-bold text-base shadow-sm shrink-0">
            P
          </div>
          {!isSidebarCollapsed && (
            <div className="flex flex-col truncate">
              <span className="font-bold text-sm tracking-tight text-text-primary">Personal OS</span>
              <span className="text-[10px] text-text-muted">Личная система</span>
            </div>
          )}
        </a>
      </div>

      {/* Main Nav Items (L1) */}
      <nav className="flex-1 px-2.5 py-4 space-y-1 overflow-y-auto" role="navigation">
        {navItems.map(renderItem)}

        {/* Less frequent sections */}
        <div className="pt-4">
          {!isSidebarCollapsed && (
            <button
              type="button"
              onClick={() => setMoreOpen((v) => !v)}
              aria-expanded={showMore}
              className="w-full flex items-center justify-between px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              <span>Ещё</span>
              <svg
                className={cn('w-3.5 h-3.5 transition-transform duration-fast', showMore && 'rotate-180')}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          )}
          {showMore && <div className="space-y-1 mt-1">{moreItems.map(renderItem)}</div>}
        </div>
      </nav>

      {/* Footer / Toggle & Settings */}
      <div className="p-3 border-t border-border space-y-1">
        <a
          href="/settings/integrations"
          title={isSidebarCollapsed ? 'Интеграции' : undefined}
          className={cn(
            'flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
            pathname.startsWith('/settings')
              ? 'bg-primary/10 text-primary-600 dark:text-primary-400 font-semibold'
              : 'text-text-muted hover:text-text-primary hover:bg-surface-muted',
            isSidebarCollapsed && 'justify-center px-0'
          )}
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          {!isSidebarCollapsed && <span>Интеграции</span>}
        </a>

        <button
          onClick={toggleSidebar}
          aria-label={isSidebarCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-muted transition-colors cursor-pointer"
        >
          <svg
            className={cn('w-4 h-4 shrink-0 transition-transform duration-fast', isSidebarCollapsed && 'rotate-180')}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="11 19 4 12 11 5" />
            <line x1="4" y1="12" x2="20" y2="12" />
          </svg>
          {!isSidebarCollapsed && <span>Свернуть панель</span>}
        </button>

        <button
          onClick={() => {
            try {
              localStorage.removeItem('personal_os_access_token');
              localStorage.removeItem('personal_os_bypass_auth');
              localStorage.removeItem('personal_os_user');
              document.cookie = 'personal_os_access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
              window.dispatchEvent(new Event('auth:logout'));
            } catch {}
            window.location.href = withBase('/login');
          }}
          title={isSidebarCollapsed ? 'Выйти' : undefined}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer',
            isSidebarCollapsed && 'justify-center px-0'
          )}
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          {!isSidebarCollapsed && <span>Выйти</span>}
        </button>
      </div>
    </aside>
  );
}
