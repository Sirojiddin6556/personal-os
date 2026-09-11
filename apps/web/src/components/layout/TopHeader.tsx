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
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement | null>(null);

  // Close notifications and profile popovers on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setIsProfileOpen(false);
      }
    };
    if (isNotifOpen || isProfileOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isNotifOpen, isProfileOpen]);

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

        {/* User Profile Avatar & Dropdown Menu */}
        <div className="relative pl-2 border-l border-border" ref={profileRef}>
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            aria-label="Меню профиля пользователя"
            className="flex items-center gap-2 group cursor-pointer focus:outline-hidden"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 via-primary to-purple-600 text-white font-bold text-xs flex items-center justify-center shadow-xs ring-2 ring-transparent group-hover:ring-primary/30 transition-all">
              S
            </div>
            <div className="hidden md:flex flex-col text-left">
              <span className="text-xs font-semibold text-text-primary leading-tight">Siroj</span>
              <span className="text-[10px] text-text-muted leading-tight">Admin</span>
            </div>
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-surface border border-border rounded-2xl shadow-xl z-50 p-2 animate-slide-in space-y-1">
              {/* User info banner */}
              <div className="px-3 py-2.5 rounded-xl bg-surface-muted/60 mb-1 border border-border/50">
                <p className="text-xs font-bold text-text-primary">Siroj</p>
                <p className="text-[11px] text-text-muted truncate">siroj@personal-os.local</p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400">Система активна</span>
                </div>
              </div>

              {/* Navigation links */}
              <Link
                href="/settings/integrations"
                onClick={() => setIsProfileOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-text-primary hover:bg-surface-muted transition-colors"
              >
                <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                <span>Интеграции и GitHub</span>
              </Link>

              <Link
                href="/planner"
                onClick={() => setIsProfileOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-text-primary hover:bg-surface-muted transition-colors"
              >
                <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                </svg>
                <span>Ежедневник и привычки</span>
              </Link>

              <a
                href="https://t.me/personal_os_bot"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setIsProfileOpen(false)}
                className="flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-text-primary hover:bg-surface-muted transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <svg className="w-4 h-4 text-[#229ED9]" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 0 0-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                  </svg>
                  <span>Telegram Бот</span>
                </div>
                <svg className="w-3 h-3 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>

              <div className="border-t border-border my-1" />

              <button
                onClick={() => {
                  setIsProfileOpen(false);
                  window.location.reload();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                <span>Перезагрузить сессию</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
