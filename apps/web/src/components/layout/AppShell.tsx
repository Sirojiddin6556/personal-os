'use client';

import React from 'react';
import { SidebarNav } from './SidebarNav';
import { TopHeader } from './TopHeader';
import { BottomTabBar } from './BottomTabBar';
import { QuickAddModal } from '../domain/quick-add/QuickAddModal';
import { useUIStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';

interface AppShellProps {
  children: React.ReactNode;
  rightPanel?: React.ReactNode;
}

export function AppShell({ children, rightPanel }: AppShellProps) {
  const { isRightPanelOpen, closeRightPanel, activeTaskId, closeTaskDetail } = useUIStore();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-text-primary">
      {/* Desktop Left Sidebar (64px collapsed / 240px expanded) */}
      <SidebarNav />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 h-screen overflow-hidden relative">
        {/* Top Header */}
        <TopHeader />

        {/* Scrollable Page Body */}
        <main
          role="main"
          className="flex-1 overflow-y-auto pb-20 lg:pb-6 focus:outline-none"
          tabIndex={-1}
        >
          {children}
        </main>

        {/* Mobile PWA Bottom Tab Bar (hides on desktop) */}
        <BottomTabBar />
      </div>

      {/* Optional Right Slide-over Panel (Context Preservation: UX principle) */}
      {(isRightPanelOpen || rightPanel) && (
        <aside
          aria-label="Боковая панель деталей"
          className={cn(
            'fixed lg:static inset-y-0 right-0 z-40 w-full sm:w-[420px] bg-surface border-l border-border shadow-xl lg:shadow-none flex flex-col transition-transform duration-slow',
            'animate-in slide-in-from-right duration-250'
          )}
        >
          <div className="h-16 px-4 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-bold text-text-primary">
              {activeTaskId ? 'Детали задачи' : 'Информация'}
            </h3>
            <button
              onClick={() => {
                closeRightPanel();
                closeTaskDetail();
              }}
              aria-label="Закрыть панель"
              className="p-1.5 text-text-muted hover:text-text-primary rounded-md hover:bg-surface-muted transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {rightPanel || (
              <div className="text-xs text-text-muted">
                {activeTaskId ? `Выбрана задача #${activeTaskId}` : 'Панель контекстных действий'}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Global Quick Add Dialog (Cmd+K / + FAB) */}
      <QuickAddModal />
    </div>
  );
}

export default AppShell;
