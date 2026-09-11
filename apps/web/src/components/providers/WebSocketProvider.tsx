'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { wsClient } from '@/lib/ws-client';
import { queryKeys } from '@/lib/query-keys';

interface WebSocketContextValue {
  isConnected: boolean;
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue>({
  isConnected: false,
  reconnect: () => {},
});

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const checkAndConnect = () => {
      const token = localStorage.getItem('personal_os_access_token');
      if (token) {
        wsClient.connect(token);
      } else {
        wsClient.disconnect();
      }
    };

    const handleConnected = () => setIsConnected(true);
    const handleDisconnected = () => setIsConnected(false);
    const handleReconnected = () => {
      setIsConnected(true);
      queryClient.invalidateQueries({ type: 'active' });
    };

    const handleAuthLogin = (e: Event) => {
      const customEvent = e as CustomEvent<{ token?: string }>;
      const token = customEvent.detail?.token || localStorage.getItem('personal_os_access_token');
      if (token) {
        wsClient.connect(token);
      }
    };

    const handleAuthLogout = () => {
      wsClient.disconnect();
      setIsConnected(false);
    };

    window.addEventListener('ws:connected', handleConnected);
    window.addEventListener('ws:disconnected', handleDisconnected);
    window.addEventListener('ws:reconnected', handleReconnected);
    window.addEventListener('auth:login', handleAuthLogin);
    window.addEventListener('auth:logout', handleAuthLogout);

    // Initial connection attempt if token exists
    checkAndConnect();

    // 1. Task domain events
    const unsubTaskUpdated = wsClient.subscribe('task.updated', (envelope) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
      if (envelope.aggregate?.id) {
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(envelope.aggregate.id) });
      }
    });

    const unsubTaskCreated = wsClient.subscribe('task.created', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    // 2. Calendar domain events
    const unsubCalendarChanged = wsClient.subscribe('calendar.event_changed', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    const unsubCalendarUpdated = wsClient.subscribe('calendar_event.updated', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    });

    // 3. Notification domain events
    const unsubNotificationCreated = wsClient.subscribe('notification.created', () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    });

    // 4. Finance domain events
    const unsubFinanceTx = wsClient.subscribe('finance.transaction.posted', () => {
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
      window.removeEventListener('auth:login', handleAuthLogin);
      window.removeEventListener('auth:logout', handleAuthLogout);

      unsubTaskUpdated();
      unsubTaskCreated();
      unsubCalendarChanged();
      unsubCalendarUpdated();
      unsubNotificationCreated();
      unsubFinanceTx();
      unsubTxPosted();
    };
  }, [queryClient]);

  const reconnect = () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('personal_os_access_token') : null;
    if (token) {
      wsClient.connect(token);
    }
  };

  return (
    <WebSocketContext.Provider value={{ isConnected, reconnect }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  return useContext(WebSocketContext);
}
