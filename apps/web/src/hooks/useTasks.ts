/**
 * @file useTasks.ts
 * @description TanStack Query hooks for tasks management, Kanban drag-and-drop,
 * and optimistic mutations with version-based If-Match concurrency headers.
 */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  InfiniteData,
} from '@tanstack/react-query';
import { apiRequest, fetchPaginated } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import {
  Task,
  TaskStatus,
  Priority,
  PaginatedResponse,
} from '@/types/domain';

export interface TaskFilterParams {
  status?: TaskStatus | string;
  project_id?: string;
  priority?: Priority | string;
  search?: string;
  limit?: number;
}

export interface CreateTaskInput {
  title: string;
  description_markdown?: string;
  status?: TaskStatus;
  priority?: Priority;
  due_date?: string | null;
  scheduled_date?: string | null;
  project_id?: string | null;
  tags?: string[];
  sort_order?: number;
  estimated_duration_minutes?: number | null;
}

export interface UpdateTaskInput {
  id: string;
  version: number;
  title?: string;
  description_markdown?: string;
  status?: TaskStatus;
  priority?: Priority;
  due_date?: string | null;
  scheduled_date?: string | null;
  project_id?: string | null;
  tags?: string[];
  sort_order?: number;
  estimated_duration_minutes?: number | null;
  actual_duration_minutes?: number | null;
  completed_at?: string | null;
}

export interface MoveTaskInput {
  id: string;
  version: number;
  status: TaskStatus;
  sort_order?: number;
}

export interface CompleteTaskInput {
  id: string;
  version: number;
}

/**
 * Hook to retrieve an infinite cursor-paginated list of tasks matching the specified filters.
 */
export function useTasksList(filters?: TaskFilterParams) {
  const query = useInfiniteQuery<PaginatedResponse<Task>, Error>({
    queryKey: queryKeys.tasks.list(filters as Record<string, unknown>),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      fetchPaginated<Task>('/tasks', {
        cursor: (pageParam as string | null) || undefined,
        limit: filters?.limit || 50,
        filters: filters as Record<string, string | number | boolean | undefined>,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more ? lastPage.pagination.next_cursor : undefined,
  });

  const tasks: Task[] = query.data?.pages.flatMap((page) => page.items) ?? [];

  return {
    tasks,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    fetchNextPage: query.fetchNextPage,
    hasNextPage: query.hasNextPage,
    isFetchingNextPage: query.isFetchingNextPage,
    refetch: query.refetch,
  };
}

/**
 * Hook to retrieve a single task by identifier.
 */
export function useTask(id: string) {
  const query = useQuery<Task, Error>({
    queryKey: queryKeys.tasks.detail(id),
    queryFn: () => apiRequest<Task>('GET', `/tasks/${id}`),
    enabled: Boolean(id),
  });

  return {
    task: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook for creating a new task with optimistic list addition and error rollback.
 */
export function useCreateTask() {
  const queryClient = useQueryClient();

  return useMutation<Task, Error, CreateTaskInput, { previousQueries: Array<[readonly unknown[], unknown]> }>({
    mutationFn: (input: CreateTaskInput) =>
      apiRequest<Task, CreateTaskInput>('POST', '/tasks', {
        body: input,
      }),
    onMutate: async (newTaskInput) => {
      // Cancel queries to prevent cache clobbering
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      // Save snapshots of matching queries for rollback
      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });

      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      // Create optimistic mock task
      const tempId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      const optimisticTask: Task = {
        id: tempId,
        workspace_id: 'local',
        title: newTaskInput.title,
        description_markdown: newTaskInput.description_markdown,
        status: newTaskInput.status || TaskStatus.INBOX,
        priority: newTaskInput.priority || Priority.P3,
        due_date: newTaskInput.due_date ?? null,
        scheduled_date: newTaskInput.scheduled_date ?? null,
        project_id: newTaskInput.project_id ?? null,
        tags: newTaskInput.tags || [],
        sort_order: newTaskInput.sort_order || 0,
        estimated_duration_minutes: newTaskInput.estimated_duration_minutes ?? null,
        actual_duration_minutes: null,
        completed_at: null,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Optimistically insert into all active task list caches
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Task>>>(
        { queryKey: queryKeys.tasks.all },
        (oldData) => {
          if (!oldData || !oldData.pages || oldData.pages.length === 0) {
            return {
              pageParams: [null],
              pages: [
                {
                  items: [optimisticTask],
                  pagination: { has_more: false, next_cursor: null },
                },
              ],
            };
          }

          const firstPage = oldData.pages[0];
          return {
            ...oldData,
            pages: [
              {
                ...firstPage,
                items: [optimisticTask, ...firstPage.items],
              },
              ...oldData.pages.slice(1),
            ],
          };
        }
      );

      return { previousQueries };
    },
    onError: (_err, _variables, context) => {
      // Rollback to previous state on failure
      context?.previousQueries.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: () => {
      // Resync state with server truth
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Mutation hook for updating task attributes with optimistic update and If-Match concurrency header.
 */
export function useUpdateTask() {
  const queryClient = useQueryClient();

  return useMutation<
    Task,
    Error,
    UpdateTaskInput,
    {
      previousDetail?: Task;
      previousQueries: Array<[readonly unknown[], unknown]>;
    }
  >({
    mutationFn: ({ id, version, ...patch }: UpdateTaskInput) =>
      apiRequest<Task, Partial<UpdateTaskInput>>('PATCH', `/tasks/${id}`, {
        body: patch,
        version,
      }),
    onMutate: async ({ id, version, ...patch }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      const previousDetail = queryClient.getQueryData<Task>(queryKeys.tasks.detail(id));
      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });
      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      // Optimistically update single detail cache
      queryClient.setQueryData<Task>(queryKeys.tasks.detail(id), (old) => {
        if (!old) return undefined;
        return {
          ...old,
          ...patch,
          version: version + 1,
          updated_at: new Date().toISOString(),
        };
      });

      // Optimistically update item in any list pages
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Task>>>(
        { queryKey: queryKeys.tasks.all },
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            pages: oldData.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === id
                  ? {
                      ...item,
                      ...patch,
                      version: version + 1,
                      updated_at: new Date().toISOString(),
                    }
                  : item
              ),
            })),
          };
        }
      );

      return { previousDetail, previousQueries };
    },
    onError: (_err, { id }, context) => {
      if (context?.previousDetail) {
        queryClient.setQueryData(queryKeys.tasks.detail(id), context.previousDetail);
      }
      context?.previousQueries.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: (_data, _error, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Hook to mark a task as DONE using optimistic update and If-Match.
 */
export function useCompleteTask() {
  const queryClient = useQueryClient();

  return useMutation<
    Task,
    Error,
    CompleteTaskInput,
    {
      previousDetail?: Task;
      previousQueries: Array<[readonly unknown[], unknown]>;
    }
  >({
    mutationFn: ({ id, version }: CompleteTaskInput) =>
      apiRequest<Task, { status: TaskStatus; completed_at: string }>('PATCH', `/tasks/${id}`, {
        body: {
          status: TaskStatus.DONE,
          completed_at: new Date().toISOString(),
        },
        version,
      }),
    onMutate: async ({ id, version }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      const previousDetail = queryClient.getQueryData<Task>(queryKeys.tasks.detail(id));
      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });
      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      const patch = {
        status: TaskStatus.DONE,
        completed_at: new Date().toISOString(),
        version: version + 1,
        updated_at: new Date().toISOString(),
      };

      queryClient.setQueryData<Task>(queryKeys.tasks.detail(id), (old) =>
        old ? { ...old, ...patch } : undefined
      );

      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Task>>>(
        { queryKey: queryKeys.tasks.all },
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            pages: oldData.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === id ? { ...item, ...patch } : item
              ),
            })),
          };
        }
      );

      return { previousDetail, previousQueries };
    },
    onError: (_err, { id }, context) => {
      if (context?.previousDetail) {
        queryClient.setQueryData(queryKeys.tasks.detail(id), context.previousDetail);
      }
      context?.previousQueries.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: (_data, _error, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Hook to handle Kanban drag-and-drop column transfers and re-ordering with optimistic feedback.
 */
export function useMoveTask() {
  const queryClient = useQueryClient();

  return useMutation<
    Task,
    Error,
    MoveTaskInput,
    {
      previousDetail?: Task;
      previousQueries: Array<[readonly unknown[], unknown]>;
    }
  >({
    mutationFn: ({ id, version, status, sort_order }: MoveTaskInput) =>
      apiRequest<Task, { status: TaskStatus; sort_order?: number }>('PATCH', `/tasks/${id}`, {
        body: { status, sort_order },
        version,
      }),
    onMutate: async ({ id, version, status, sort_order }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      const previousDetail = queryClient.getQueryData<Task>(queryKeys.tasks.detail(id));
      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });
      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      const patch: Partial<Task> = {
        status,
        ...(sort_order !== undefined ? { sort_order } : {}),
        version: version + 1,
        updated_at: new Date().toISOString(),
      };

      queryClient.setQueryData<Task>(queryKeys.tasks.detail(id), (old) =>
        old ? { ...old, ...patch } : undefined
      );

      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Task>>>(
        { queryKey: queryKeys.tasks.all },
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            pages: oldData.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === id ? { ...item, ...patch } : item
              ),
            })),
          };
        }
      );

      return { previousDetail, previousQueries };
    },
    onError: (_err, { id }, context) => {
      if (context?.previousDetail) {
        queryClient.setQueryData(queryKeys.tasks.detail(id), context.previousDetail);
      }
      context?.previousQueries.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: (_data, _error, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    },
  });
}
