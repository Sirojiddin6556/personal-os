import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from '@/stores/ui-store';

describe('useUIStore', () => {
  beforeEach(() => {
    // Reset store to default state before each test
    useUIStore.setState({
      sidebarCollapsed: false,
      isSidebarCollapsed: false,
      activeModal: null,
      isQuickAddOpen: false,
      isRightPanelOpen: false,
      theme: 'system',
      activeTaskId: null,
      quickAddInitialType: 'task',
    });
  });

  it('has valid default state', () => {
    const state = useUIStore.getState();
    expect(state.sidebarCollapsed).toBe(false);
    expect(state.isSidebarCollapsed).toBe(false);
    expect(state.activeModal).toBeNull();
    expect(state.isQuickAddOpen).toBe(false);
    expect(state.isRightPanelOpen).toBe(false);
    expect(state.theme).toBe('system');
    expect(state.activeTaskId).toBeNull();
    expect(state.quickAddInitialType).toBe('task');
  });

  describe('sidebar management', () => {
    it('toggles sidebar collapsed state and syncs isSidebarCollapsed', () => {
      const { toggleSidebar } = useUIStore.getState();

      toggleSidebar();
      expect(useUIStore.getState().sidebarCollapsed).toBe(true);
      expect(useUIStore.getState().isSidebarCollapsed).toBe(true);

      toggleSidebar();
      expect(useUIStore.getState().sidebarCollapsed).toBe(false);
      expect(useUIStore.getState().isSidebarCollapsed).toBe(false);
    });

    it('explicitly sets sidebar collapsed via setSidebarCollapsed', () => {
      const { setSidebarCollapsed } = useUIStore.getState();

      setSidebarCollapsed(true);
      expect(useUIStore.getState().sidebarCollapsed).toBe(true);
      expect(useUIStore.getState().isSidebarCollapsed).toBe(true);

      setSidebarCollapsed(false);
      expect(useUIStore.getState().sidebarCollapsed).toBe(false);
      expect(useUIStore.getState().isSidebarCollapsed).toBe(false);
    });
  });

  describe('modal transitions & quick add', () => {
    it('opens quick-add modal and configures quick add state', () => {
      const { openModal } = useUIStore.getState();

      openModal('quick-add', { initialType: 'expense' });

      const state = useUIStore.getState();
      expect(state.activeModal).toBe('quick-add');
      expect(state.isQuickAddOpen).toBe(true);
      expect(state.isRightPanelOpen).toBe(false);
      expect(state.quickAddInitialType).toBe('expense');
      expect(state.activeTaskId).toBeNull();
    });

    it('opens task-detail modal and stores active task ID', () => {
      const { openModal } = useUIStore.getState();

      openModal('task-detail', { taskId: 'task-uuid-42' });

      const state = useUIStore.getState();
      expect(state.activeModal).toBe('task-detail');
      expect(state.isRightPanelOpen).toBe(true);
      expect(state.isQuickAddOpen).toBe(false);
      expect(state.activeTaskId).toBe('task-uuid-42');
    });

    it('closes modal and clears active task id and flags', () => {
      const { openModal, closeModal } = useUIStore.getState();

      openModal('task-detail', { taskId: 'task-uuid-42' });
      expect(useUIStore.getState().activeModal).toBe('task-detail');

      closeModal();
      const state = useUIStore.getState();
      expect(state.activeModal).toBeNull();
      expect(state.isQuickAddOpen).toBe(false);
      expect(state.isRightPanelOpen).toBe(false);
      expect(state.activeTaskId).toBeNull();
    });
  });

  describe('theme mode', () => {
    it('switches themes between light, dark, and system', () => {
      const { setTheme } = useUIStore.getState();

      setTheme('dark');
      expect(useUIStore.getState().theme).toBe('dark');

      setTheme('light');
      expect(useUIStore.getState().theme).toBe('light');

      setTheme('system');
      expect(useUIStore.getState().theme).toBe('system');
    });
  });

  describe('convenience helper methods', () => {
    it('openQuickAdd sets quick add intent and opens modal', () => {
      const { openQuickAdd } = useUIStore.getState();

      openQuickAdd('event');
      const state = useUIStore.getState();
      expect(state.activeModal).toBe('quick-add');
      expect(state.isQuickAddOpen).toBe(true);
      expect(state.quickAddInitialType).toBe('event');
    });

    it('closeQuickAdd closes quick add modal', () => {
      const { openQuickAdd, closeQuickAdd } = useUIStore.getState();

      openQuickAdd('task');
      expect(useUIStore.getState().isQuickAddOpen).toBe(true);

      closeQuickAdd();
      expect(useUIStore.getState().isQuickAddOpen).toBe(false);
      expect(useUIStore.getState().activeModal).toBeNull();
    });

    it('openTaskDetail and closeTaskDetail manage right panel and active taskId', () => {
      const { openTaskDetail, closeTaskDetail } = useUIStore.getState();

      openTaskDetail('test-task-123');
      expect(useUIStore.getState().activeModal).toBe('task-detail');
      expect(useUIStore.getState().isRightPanelOpen).toBe(true);
      expect(useUIStore.getState().activeTaskId).toBe('test-task-123');

      closeTaskDetail();
      expect(useUIStore.getState().activeModal).toBeNull();
      expect(useUIStore.getState().isRightPanelOpen).toBe(false);
      expect(useUIStore.getState().activeTaskId).toBeNull();
    });

    it('openRightPanel and closeRightPanel control panel visibility', () => {
      const { openRightPanel, closeRightPanel } = useUIStore.getState();

      openRightPanel();
      expect(useUIStore.getState().isRightPanelOpen).toBe(true);

      closeRightPanel();
      expect(useUIStore.getState().isRightPanelOpen).toBe(false);
    });
  });
});
