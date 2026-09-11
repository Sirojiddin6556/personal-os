/**
 * @file ws-client.ts
 * @description Resilient WebSocket client singleton with Full Jitter exponential backoff,
 * 30-second heartbeat ping/pong, and automatic TanStack Query cache compensation upon reconnection.
 */

import { queryClient } from './query-client';
import { queryKeys } from './query-keys';

/**
 * Standard transactional outbox event envelope delivered over WebSocket.
 */
export interface WebSocketEnvelope<TData = unknown> {
  event_id: string;
  event_type: string;
  occurred_at: string;
  workspace_id: string;
  actor: {
    actor_id: string;
    actor_type: 'user' | 'ai_agent' | 'system' | 'integration' | string;
  };
  aggregate: {
    id: string;
    type: string;
    version: number;
  };
  correlation_id: string;
  data: TData;
}

/**
 * WebSocket incoming event listener callback signature.
 */
export type EventHandler<TData = unknown> = (event: WebSocketEnvelope<TData>) => void;

/**
 * WebSocket client manager maintaining lifecycle, heartbeat, and reconnection.
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 15;
  private readonly baseDelay = 1000; // 1s
  private readonly maxDelay = 30000; // 30s
  private pingIntervalId: ReturnType<typeof setInterval> | null = null;
  private pongTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private handlers = new Map<string, Set<EventHandler<any>>>();
  private isExplicitlyClosed = false;
  private hasConnectedBefore = false;
  private lastEventOccurredAt: string | null = null;

  /**
   * Initializes or updates connection to the /v1/ws endpoint.
   *
   * @param token Bearer JWT authentication token.
   */
  public connect(token?: string): void {
    if (typeof window === 'undefined') return;

    if (token) {
      this.token = token;
    } else if (!this.token) {
      this.token = localStorage.getItem('personal_os_access_token');
    }

    if (!this.token) {
      console.warn('[WebSocketClient] No authentication token provided. Deferring connection.');
      return;
    }

    this.isExplicitlyClosed = false;

    // Terminate existing socket if any
    this.closeSocket();

    let wsUrl: string;
    if (process.env.NEXT_PUBLIC_WS_URL) {
      const baseWs = process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '');
      const fullWs = baseWs.endsWith('/v1/ws') ? baseWs : `${baseWs}/v1/ws`;
      wsUrl = `${fullWs}?token=${encodeURIComponent(this.token)}`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${window.location.host}/v1/ws?token=${encodeURIComponent(this.token)}`;
    }

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupListeners();
    } catch (err) {
      console.error('[WebSocketClient] Connection failed to initialize:', err);
      this.scheduleReconnect();
    }
  }

  /**
   * Registers a callback handler for a specific event type or all events ('*').
   *
   * @param eventType Domain event type string (e.g. 'task.updated') or '*'.
   * @param handler Listener function.
   * @returns Cleanup unsubscribe function.
   */
  public subscribe<TData = unknown>(
    eventType: string,
    handler: EventHandler<TData>
  ): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }

    const set = this.handlers.get(eventType)!;
    set.add(handler as EventHandler<any>);

    return () => {
      set.delete(handler as EventHandler<any>);
      if (set.size === 0) {
        this.handlers.delete(eventType);
      }
    };
  }

  /**
   * Closes active connection and disables automatic reconnection.
   */
  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.clearTimers();
    this.closeSocket();
  }

  /**
   * Returns current ready state of the socket.
   */
  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private setupListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.info('[WebSocketClient] Connected to Personal OS real-time stream.');
      this.reconnectAttempts = 0;
      this.startHeartbeat();

      // If this is a re-connection after network disruption, compensate query cache
      if (this.hasConnectedBefore) {
        this.compensateMissedEvents();
      }
      this.hasConnectedBefore = true;

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('ws:connected'));
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);

        // Heartbeat response handling
        if (payload.type === 'pong') {
          if (this.pongTimeoutId) {
            clearTimeout(this.pongTimeoutId);
            this.pongTimeoutId = null;
          }
          return;
        }

        // Domain event envelope
        const envelope = payload as WebSocketEnvelope;
        if (envelope.occurred_at) {
          this.lastEventOccurredAt = envelope.occurred_at;
        }

        this.dispatchEvent(envelope);
      } catch (err) {
        console.warn('[WebSocketClient] Could not parse inbound WebSocket message:', event.data, err);
      }
    };

    this.ws.onerror = (err) => {
      console.warn('[WebSocketClient] Socket error encountered:', err);
    };

    this.ws.onclose = (event: CloseEvent) => {
      this.clearTimers();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('ws:disconnected', { detail: { code: event.code } }));
      }

      if (!this.isExplicitlyClosed) {
        console.warn(`[WebSocketClient] Socket closed (code ${event.code}). Scheduling reconnection.`);
        this.scheduleReconnect();
      }
    };
  }

  private dispatchEvent(envelope: WebSocketEnvelope): void {
    // 1. Notify typed listeners
    const specificHandlers = this.handlers.get(envelope.event_type);
    specificHandlers?.forEach((handler) => {
      try {
        handler(envelope);
      } catch (err) {
        console.error(`[WebSocketClient] Error in listener for ${envelope.event_type}:`, err);
      }
    });

    // Notify wildcard '*' listeners
    const wildcardHandlers = this.handlers.get('*');
    wildcardHandlers?.forEach((handler) => {
      try {
        handler(envelope);
      } catch (err) {
        console.error('[WebSocketClient] Error in wildcard listener:', err);
      }
    });

    // 2. Perform automated TanStack Query cache invalidations
    this.routeToQueryCache(envelope);
  }

  /**
   * Maps domain events to relevant TanStack Query keys for automatic cache invalidation.
   */
  private routeToQueryCache(envelope: WebSocketEnvelope): void {
    const { event_type, aggregate } = envelope;

    switch (event_type) {
      // Task domain events
      case 'task.created':
      case 'task.updated':
      case 'task.status_changed':
      case 'task.rescheduled':
      case 'task.completed':
      case 'task.deleted':
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
        if (aggregate?.id) {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(aggregate.id) });
        }
        break;

      // Calendar events
      case 'calendar_event.created':
      case 'calendar_event.updated':
      case 'calendar_event.deleted':
      case 'calendar.event_changed':
      case 'timeblock.allocated':
      case 'timeblock.released':
        queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
        break;

      // Finance transactions & budgets
      case 'transaction.posted':
      case 'finance.transaction.posted':
      case 'budget.threshold_exceeded':
        queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
        break;

      // Habit logs & streaks
      case 'habit.created':
      case 'habit.logged':
      case 'habit.streak_reset':
      case 'habit.streak_milestone_reached':
        queryClient.invalidateQueries({ queryKey: queryKeys.habits.all });
        break;

      // Notifications
      case 'notification.created':
      case 'notification.dispatched':
        queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('notification:received', { detail: envelope.data }));
        }
        break;

      // AI proposals
      case 'ai.action_proposed':
      case 'ai.action_confirmed':
      case 'ai.action_rejected':
        queryClient.invalidateQueries({ queryKey: queryKeys.advisor.plans() });
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('ai:proposal_received', { detail: envelope.data }));
        }
        break;

      default:
        break;
    }
  }

  /**
   * Invalidates active queries upon reconnection to ensure UI state parity.
   */
  private compensateMissedEvents(): void {
    console.info(
      `[WebSocketClient] Reconnected. Invalidating queries to compensate missed events (last seen: ${this.lastEventOccurredAt || 'initial'}).`
    );
    queryClient.invalidateQueries({ type: 'active' });
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('ws:reconnected'));
    }
  }

  /**
   * Starts a 30-second ping heartbeat and monitors 10-second pong response.
   */
  private startHeartbeat(): void {
    this.clearHeartbeat();

    this.pingIntervalId = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));

        // If pong is not received within 10s, consider socket stale and reconnect
        this.pongTimeoutId = setTimeout(() => {
          console.warn('[WebSocketClient] Heartbeat pong timeout (10s). Terminating stalled connection.');
          this.closeSocket();
          this.scheduleReconnect();
        }, 10000);
      }
    }, 30000);
  }

  private clearHeartbeat(): void {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
    if (this.pongTimeoutId) {
      clearTimeout(this.pongTimeoutId);
      this.pongTimeoutId = null;
    }
  }

  private clearTimers(): void {
    this.clearHeartbeat();
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  private closeSocket(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      try {
        this.ws.close();
      } catch {
        // Ignore close exceptions
      }
      this.ws = null;
    }
  }

  /**
   * Calculates exponential backoff with Full Jitter (1s -> 30s max).
   */
  private scheduleReconnect(): void {
    if (this.isExplicitlyClosed) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocketClient] Max reconnect attempts reached. Awaiting manual reconnection.');
      return;
    }

    // Full Jitter: delay = min(maxDelay, baseDelay * (1.5 ^ attempt))
    const exponential = Math.min(
      this.maxDelay,
      this.baseDelay * Math.pow(1.5, this.reconnectAttempts)
    );
    // +/- 20% random jitter
    const jitter = exponential * 0.2 * (Math.random() * 2 - 1);
    const finalDelay = Math.max(1000, Math.min(this.maxDelay, Math.floor(exponential + jitter)));

    this.reconnectAttempts++;
    console.info(
      `[WebSocketClient] Reconnecting in ${finalDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
    }

    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, finalDelay);
  }
}

/**
 * Singleton WebSocket client instance for Personal OS.
 */
export const wsClient = new WebSocketClient();
