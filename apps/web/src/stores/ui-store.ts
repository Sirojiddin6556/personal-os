/**
 * @file ui-store.ts
 * @description Ephemeral client UI state managed via Zustand (< 2KB footprint).
 * Strictly isolated from server state (no domain entities stored here).
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export type ModalType = 'quick-add' | 'task-detail' | null;
export type ThemeMode = 'light' | 'dark' | 'system';
export type QuickAddIntentType = 'task' | 'event' | 'expense';

export interface OpenModalOptions {
  taskId?: string;
  initialType?: QuickAddIntentType;
}

export interface UIStore {
  // State
  sidebarCollapsed: boolean;
  isSidebarCollapsed: boolean; // Convenience alias
  activeModal: ModalType;
  isQuickAddOpen: boolean;     // Convenience alias
  isRightPanelOpen: boolean;   // Convenience alias
  theme: ThemeMode;
  activeTaskId: string | null;
  quickAddInitialType: QuickAddIntentType;

  // Core Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openModal: (modal: Exclude<ModalType, null>, options?: OpenModalOptions) => void;
  closeModal: () => void;
  setTheme: (theme: ThemeMode) => void;

  // Convenience Actions for UI Components
  openQuickAdd: (initialType?: QuickAddIntentType) => void;
  closeQuickAdd: () => void;
  openTaskDetail: (taskId: string) => void;
  closeTaskDetail: () => void;
  openRightPanel: () => void;
  closeRightPanel: () => void;
}

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set) => ({
        // Initial state
        sidebarCollapsed: false,
        isSidebarCollapsed: false,
        activeModal: null,
        isQuickAddOpen: false,
        isRightPanelOpen: false,
        theme: 'system',
        activeTaskId: null,
        quickAddInitialType: 'task',

        // Actions
        toggleSidebar: () =>
          set((state) => ({
            sidebarCollapsed: !state.sidebarCollapsed,
            isSidebarCollapsed: !state.sidebarCollapsed,
          })),

        setSidebarCollapsed: (collapsed: boolean) =>
          set({
            sidebarCollapsed: collapsed,
            isSidebarCollapsed: collapsed,
          }),

        openModal: (modal, options) =>
          set({
            activeModal: modal,
            isQuickAddOpen: modal === 'quick-add',
            isRightPanelOpen: modal === 'task-detail',
            activeTaskId: options?.taskId ?? null,
            quickAddInitialType: options?.initialType ?? 'task',
          }),

        closeModal: () =>
          set({
            activeModal: null,
            isQuickAddOpen: false,
            isRightPanelOpen: false,
            activeTaskId: null,
          }),

        setTheme: (theme: ThemeMode) =>
          set({ theme }),

        // Convenience methods
        openQuickAdd: (initialType = 'task') =>
          set({
            activeModal: 'quick-add',
            isQuickAddOpen: true,
            quickAddInitialType: initialType,
          }),

        closeQuickAdd: () =>
          set({
            activeModal: null,
            isQuickAddOpen: false,
          }),

        openTaskDetail: (taskId: string) =>
          set({
            activeModal: 'task-detail',
            isRightPanelOpen: true,
            activeTaskId: taskId,
          }),

        closeTaskDetail: () =>
          set({
            activeModal: null,
            isRightPanelOpen: false,
            activeTaskId: null,
          }),

        openRightPanel: () =>
          set({
            isRightPanelOpen: true,
          }),

        closeRightPanel: () =>
          set({
            isRightPanelOpen: false,
            activeTaskId: null,
          }),
      }),
      {
        name: 'personal-os-ui-state',
        // Persist only user layout preferences across browser reloads
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          theme: state.theme,
        }),
      }
    )
  )
);
