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
  activeModal: ModalType;
  theme: ThemeMode;
  activeTaskId: string | null;
  quickAddInitialType: QuickAddIntentType;

  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openModal: (modal: Exclude<ModalType, null>, options?: OpenModalOptions) => void;
  closeModal: () => void;
  setTheme: (theme: ThemeMode) => void;
}

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set) => ({
        // Initial state
        sidebarCollapsed: false,
        activeModal: null,
        theme: 'system',
        activeTaskId: null,
        quickAddInitialType: 'task',

        // Actions
        toggleSidebar: () =>
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

        setSidebarCollapsed: (collapsed: boolean) =>
          set({ sidebarCollapsed: collapsed }),

        openModal: (modal, options) =>
          set({
            activeModal: modal,
            activeTaskId: options?.taskId ?? null,
            quickAddInitialType: options?.initialType ?? 'task',
          }),

        closeModal: () =>
          set({
            activeModal: null,
            activeTaskId: null,
          }),

        setTheme: (theme: ThemeMode) =>
          set({ theme }),
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
