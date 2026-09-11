/**
 * @file useNotifications.ts
 * @description Hook for querying, managing, and acknowledging user notifications with real-time updates.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { Notification, UnreadCountResponse } from '@/types/domain';

export function useNotifications() {
  const queryClient = useQueryClient();

  // List notifications
  const listQuery = useQuery<Notification[], Error>({
    queryKey: queryKeys.notifications.list(),
    queryFn: () =>
      apiRequest<Notification[]>('GET', '/notifications'),
    staleTime: 1000 * 30, // 30s
  });

  // Unread count query
  const countQuery = useQuery<UnreadCountResponse, Error>({
    queryKey: queryKeys.notifications.unreadCount(),
    queryFn: () =>
      apiRequest<UnreadCountResponse>('GET', '/notifications/unread-count'),
    staleTime: 1000 * 15, // 15s
    refetchInterval: 30000,
  });

  // Mark single notification as read
  const markReadMutation = useMutation<Notification, Error, string>({
    mutationFn: (notificationId: string) =>
      apiRequest<Notification>('PATCH', `/notifications/${notificationId}/read`),
    onSuccess: (updated) => {
      // Invalidate both count and list
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
      queryClient.setQueryData<Notification[]>(queryKeys.notifications.list(), (prev) => {
        if (!prev) return [updated];
        return prev.map((item) => (item.id === updated.id ? updated : item));
      });
      queryClient.setQueryData<UnreadCountResponse>(queryKeys.notifications.unreadCount(), (prev) => {
        if (!prev) return { unread_count: 0 };
        return { unread_count: Math.max(0, prev.unread_count - 1) };
      });
    },
  });

  // Mark all read mutation helper
  const markAllReadMutation = useMutation<void, Error, void>({
    mutationFn: async () => {
      const items = listQuery.data || [];
      const unreadItems = items.filter((n) => !n.read_at && n.status !== 'read');
      await Promise.all(
        unreadItems.map((n) => apiRequest('PATCH', `/notifications/${n.id}/read`))
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
  });

  const notifications = listQuery.data ?? [];
  const unreadCount = countQuery.data?.unread_count ?? notifications.filter((n) => !n.read_at && n.status !== 'read').length;

  return {
    notifications,
    unreadCount,
    isLoading: listQuery.isLoading || countQuery.isLoading,
    isError: listQuery.isError || countQuery.isError,
    markRead: (id: string) => markReadMutation.mutateAsync(id),
    markAllRead: () => markAllReadMutation.mutateAsync(),
    refetch: () => {
      listQuery.refetch();
      countQuery.refetch();
    },
  };
}
