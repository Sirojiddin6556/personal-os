'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useUIStore } from '@/stores/ui-store';
import { useNotifications } from '@/hooks/useNotifications';
import { formatDateShort } from '@/lib/utils';
import Link from 'next/link';

export function TopHeader() {
  const { openQuickAdd, theme, setTheme } = useUIStore();
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement | null>(null);

  // Close notifications popover on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false);
      }
    };
    if (isNotifOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isNotifOpen]);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openQuickAdd();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [openQuickAdd]);

  return (
    <header
      role="banner"
      className="h-16 border-b border-border bg-surface px-4 lg:px-6 flex items-center justify-between sticky top-0 z-20"
    >
      {/* Search / Quick Add Trigger Bar */}
      <div className="flex items-center gap-3 flex-1 max-w-lg">
        <button
          onClick={() => openQuickAdd()}
          className="w-full flex items-center justify-between px-3.5 py-2 bg-surface-muted hover:bg-surface border border-border hover:border-primary/40 rounded-xl text-xs text-text-muted transition-all shadow-xs group cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-text-muted group-hover:text-primary transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span>Быстрый поиск или добавление задачи...</span>
          </div>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-text-muted bg-surface border border-border rounded shadow-2xs">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Quick Add CTA button */}
        <button
          onClick={() => openQuickAdd()}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 active:scale-95 transition-all shadow-xs cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Создать</span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          aria-label="Переключить тему оформления"
          className="p-2 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-muted transition-colors cursor-pointer"
        >
          {theme === 'dark' ? (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>

        {/* Notification Bell & Dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setIsNotifOpen(!isNotifOpen)}
            aria-label={`Уведомления ${unreadCount > 0 ? `(${unreadCount} новых)` : ''}`}
            className="relative p-2 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-muted transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-primary text-white text-[10px] font-bold rounded-full flex items-center justify-center ring-2 ring-surface">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {isNotifOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-surface border border-border rounded-2xl shadow-xl z-50 p-4 space-y-3 animate-slide-in">
              <div className="flex items-center justify-between border-b border-border pb-2.5">
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text-primary">
                    Уведомления
                  </h3>
                  {unreadCount > 0 && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                      {unreadCount} новых
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllRead()}
                    className="text-[11px] text-primary hover:underline font-medium"
                  >
                    Прочитать все
                  </button>
                )}
              </div>

              <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
                {notifications.length > 0 ? (
                  notifications.map((n) => {
                    const isUnread = !n.read_at && n.status !== 'read';
                    return (
                      <div
                        key={n.id}
                        onClick={() => {
                          if (isUnread) markRead(n.id);
                        }}
                        className={`p-2.5 rounded-xl border text-xs transition-colors cursor-pointer ${
                          isUnread
                            ? 'bg-primary/5 border-primary/20 text-text-primary font-medium'
                            : 'bg-surface-muted/50 border-border text-text-muted'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-text-primary truncate">
                            {n.title}
                          </span>
                          {n.created_at && (
                            <span className="text-[10px] text-text-muted shrink-0">
                              {formatDateShort(n.created_at)}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-text-secondary mt-0.5 line-clamp-2">
                          {n.message || n.body || ''}
                        </p>
                      </div>
                    );
                  })
                ) : (
                  <div className="py-6 text-center text-xs text-text-muted">
                    Нет новых уведомлений
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile Avatar / Settings Link */}
        <Link
          href="/settings/integrations"
          title="Настройки интеграций"
          className="flex items-center gap-2 pl-2 border-l border-border hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shadow-xs">
            S
          </div>
        </Link>
      </div>
    </header>
  );
}
