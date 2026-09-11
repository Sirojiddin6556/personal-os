/**
 * @file useWebSocket.ts
 * @description React hook that initializes real-time WebSocket connection,
 * listens to core domain events, and invalidates TanStack Query caches automatically.
 */

import { useEffect, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { wsClient, EventHandler, WebSocketEnvelope } from '@/lib/ws-client';
import { queryKeys } from '@/lib/query-keys';

export interface UseWebSocketOptions {
  /** Optional explicit bearer token */
  token?: string;
  /** Whether to connect automatically on mount (default: true) */
  autoConnect?: boolean;
}

/**
 * Hook to manage WebSocket lifecycle, listen for real-time events,
 * and keep TanStack Query caches in sync with backend state mutations.
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { token, autoConnect = true } = options;
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState<boolean>(() => wsClient.isConnected());

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleConnected = () => setIsConnected(true);
    const handleDisconnected = () => setIsConnected(false);
    const handleReconnected = () => {
      setIsConnected(true);
      // Ensure all queries are refreshed on reconnect
      queryClient.invalidateQueries({ type: 'active' });
    };

    window.addEventListener('ws:connected', handleConnected);
    window.addEventListener('ws:disconnected', handleDisconnected);
    window.addEventListener('ws:reconnected', handleReconnected);

    // Initial connection
    if (autoConnect) {
      wsClient.connect(token);
    }

    // 1. Task events subscription
    const unsubTask = wsClient.subscribe('task.updated', (event) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
      if (event.aggregate?.id) {
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(event.aggregate.id) });
      }
    });

    const unsubTaskCreated = wsClient.subscribe('task.created', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    const unsubTaskStatus = wsClient.subscribe('task.status_changed', (event) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
      if (event.aggregate?.id) {
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(event.aggregate.id) });
      }
    });

    // 2. Calendar events subscription
    const unsubCalendar = wsClient.subscribe('calendar.event_changed', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    const unsubCalendarEventUpdated = wsClient.subscribe('calendar_event.updated', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    // 3. Notification events subscription
    const unsubNotification = wsClient.subscribe('notification.created', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    });

    const unsubNotificationDispatched = wsClient.subscribe('notification.dispatched', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    });

    // 4. Finance events subscription
    const unsubFinance = wsClient.subscribe('finance.transaction.posted', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    const unsubTxPosted = wsClient.subscribe('transaction.posted', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    return () => {
      window.removeEventListener('ws:connected', handleConnected);
      window.removeEventListener('ws:disconnected', handleDisconnected);
      window.removeEventListener('ws:reconnected', handleReconnected);

      unsubTask();
      unsubTaskCreated();
      unsubTaskStatus();
      unsubCalendar();
      unsubCalendarEventUpdated();
      unsubNotification();
      unsubNotificationDispatched();
      unsubFinance();
      unsubTxPosted();
    };
  }, [token, autoConnect, queryClient]);

  /**
   * Helper to subscribe to custom domain events directly from components.
   */
  const subscribe = useCallback(
    <TData = unknown>(eventType: string, handler: EventHandler<TData>) => {
      return wsClient.subscribe(eventType, handler);
    },
    []
  );

  /**
   * Manually triggers socket reconnection.
   */
  const connect = useCallback(
    (customToken?: string) => {
      wsClient.connect(customToken || token);
    },
    [token]
  );

  /**
   * Manually closes socket connection.
   */
  const disconnect = useCallback(() => {
    wsClient.disconnect();
    setIsConnected(false);
  }, []);

  return {
    isConnected,
    subscribe,
    connect,
    disconnect,
  };
}
