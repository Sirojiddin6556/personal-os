/**
 * @file useCalendar.ts
 * @description TanStack Query hooks for managing calendar events, allocating timeblocks for tasks,
 * and monitoring Google Calendar two-way synchronization status.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { CalendarEvent, TimeBlock } from '@/types/domain';

export interface CreateEventInput {
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  is_all_day?: boolean;
  rrule?: string | null;
  location?: string | null;
  task_id?: string | null;
}

export interface CreateTimeBlockInput {
  task_id?: string | null;
  start_time?: string;
  end_time?: string;
  starts_at?: string;
  ends_at?: string;
  label?: string | null;
  is_locked?: boolean;
  is_fixed?: boolean;
}

export interface GoogleSyncStatusResponse {
  status: 'idle' | 'syncing' | 'connected' | 'error' | 'disconnected';
  last_sync: string | null;
  synced_events_count?: number;
  error_message?: string | null;
}

/**
 * Hook to retrieve calendar events within an ISO timestamp range.
 *
 * @param from ISO UTC start range (defaults to start of current week if omitted).
 * @param to ISO UTC end range (defaults to end of current week if omitted).
 */
export function useCalendarEvents(from?: string, to?: string) {
  const query = useQuery<CalendarEvent[], Error>({
    queryKey: queryKeys.calendar.events({ from, to }),
    queryFn: () =>
      apiRequest<CalendarEvent[]>('GET', '/calendar/events', {
        params: { from, to },
      }),
    enabled: Boolean(from && to),
  });

  return {
    events: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook to create a new calendar event.
 */
export function useCreateEvent() {
  const queryClient = useQueryClient();

  return useMutation<CalendarEvent, Error, CreateEventInput>({
    mutationFn: (input: CreateEventInput) =>
      apiRequest<CalendarEvent, CreateEventInput>('POST', '/calendar/events', {
        body: input,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Mutation hook to allocate a focused timeblock for a specific task.
 */
export function useCreateTimeBlock() {
  const queryClient = useQueryClient();

  return useMutation<TimeBlock, Error, CreateTimeBlockInput>({
    mutationFn: (input: CreateTimeBlockInput) =>
      apiRequest<TimeBlock, CreateTimeBlockInput>('POST', '/calendar/timeblocks', {
        body: input,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Hook to observe Google Calendar synchronization status and last sync timestamp.
 */
export function useGoogleSyncStatus() {
  const queryClient = useQueryClient();

  const query = useQuery<GoogleSyncStatusResponse, Error>({
    queryKey: queryKeys.calendar.syncStatus(),
    queryFn: () =>
      apiRequest<GoogleSyncStatusResponse>('GET', '/integrations/google/sync-status'),
    refetchInterval: (queryState) => {
      // Poll every 5s if actively syncing, else every 60s
      return queryState.state.data?.status === 'syncing' ? 5000 : 60000;
    },
  });

  const triggerSyncMutation = useMutation<{ job_id: string; status: string }, Error>({
    mutationFn: () =>
      apiRequest<{ job_id: string; status: string }>('POST', '/integrations/google/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.syncStatus() });
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
    },
  });

  return {
    status: query.data?.status ?? 'idle',
    lastSync: query.data?.last_sync ?? null,
    errorMessage: query.data?.error_message ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    triggerSync: triggerSyncMutation.mutateAsync,
    isSyncing: triggerSyncMutation.isPending || query.data?.status === 'syncing',
  };
}
