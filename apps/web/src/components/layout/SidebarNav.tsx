'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useUIStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';

import { useProjects } from '@/hooks/useGitHub';

export function SidebarNav() {
  const pathname = usePathname() || '/today';
  const { isSidebarCollapsed, toggleSidebar } = useUIStore();
  const { data: dbProjects = [] } = useProjects();

  const navItems = [
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
      label: 'Проекты & GitHub',
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
              <span className="text-[10px] text-text-muted">AI Workspace</span>
            </div>
          )}
        </a>
      </div>

      {/* Main Nav Items (L1) */}
      <nav className="flex-1 px-2.5 py-4 space-y-1 overflow-y-auto" role="navigation">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <a
              key={item.href}
              href={item.href}
              title={isSidebarCollapsed ? item.label : undefined}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-fast',
                isActive
                  ? 'bg-primary/10 text-primary-600 dark:text-primary-400 font-semibold'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-muted',
                isSidebarCollapsed && 'justify-center px-0'
              )}
            >
              {item.icon}
              {!isSidebarCollapsed && (
                <span className="truncate flex-1">{item.label}</span>
              )}
              {!isSidebarCollapsed && item.badge && (
                <span className="px-1.5 py-0.5 text-[11px] font-bold rounded-full bg-primary/20 text-primary-700 dark:text-primary-300">
                  {item.badge}
                </span>
              )}
            </a>
          );
        })}

        {/* L2 Projects Section */}
        {!isSidebarCollapsed && (
          <div className="pt-6 pb-2">
            <div className="px-3 text-[11px] font-bold uppercase tracking-wider text-text-muted mb-2 flex items-center justify-between">
              <span>Проекты</span>
              <a
                href="/projects"
                className="hover:text-text-primary transition-colors text-xs font-bold"
                title="Управление проектами"
              >
                +
              </a>
            </div>
            <div className="space-y-0.5">
              {dbProjects.length > 0 ? (
                dbProjects.map((proj) => (
                  <a
                    key={proj.id}
                    href={`/projects?id=${proj.id}`}
                    className="flex items-center gap-2.5 px-3 py-1.5 rounded-md text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: proj.color || '#6366f1' }}
                    />
                    <span className="truncate flex-1">{proj.name}</span>
                    {proj.github_repo && (
                      <span className="text-[9px] px-1 py-0.2 rounded bg-surface-muted text-text-muted font-mono">
                        git
                      </span>
                    )}
                  </a>
                ))
              ) : (
                <a
                  href="/projects"
                  className="px-3 py-1.5 text-xs text-text-muted hover:text-text-primary block transition-colors italic"
                >
                  + Добавить проект
                </a>
              )}
            </div>
          </div>
        )}
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
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-muted transition-colors"
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
      </div>
    </aside>
  );
}
