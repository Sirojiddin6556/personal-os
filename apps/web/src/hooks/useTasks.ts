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
import React from 'react';
import {
  Task,
  TaskAttachment,
  TaskStatus,
  TaskStatusType,
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
  status?: TaskStatus;
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
        limit: filters?.limit || 200,
        filters: filters as Record<string, string | number | boolean | undefined>,
      }),
    getNextPageParam: (lastPage) =>
      lastPage?.pagination?.has_more ? lastPage.pagination.next_cursor : undefined,
  });

  const { data, hasNextPage, fetchNextPage } = query;

  React.useEffect(() => {
    if (hasNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, fetchNextPage]);

  const tasks: Task[] = React.useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data]
  );

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
    mutationFn: ({ id, version, status = TaskStatus.DONE }: CompleteTaskInput) =>
      apiRequest<Task, { status: TaskStatus; completed_at: string | null }>('PATCH', `/tasks/${id}`, {
        body: {
          status,
          completed_at: status === TaskStatus.DONE ? new Date().toISOString() : null,
        },
        version,
      }),
    onMutate: async ({ id, version, status = TaskStatus.DONE }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      const previousDetail = queryClient.getQueryData<Task>(queryKeys.tasks.detail(id));
      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });
      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      const patch = {
        status,
        completed_at: status === TaskStatus.DONE ? new Date().toISOString() : null,
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

/**
 * Mutation hook for deleting a task with optimistic cache eviction.
 */
export function useDeleteTask() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { id: string; version?: number }, { previousQueries: Array<[readonly unknown[], unknown]> }>({
    mutationFn: ({ id, version }: { id: string; version?: number }) =>
      apiRequest<void>('DELETE', `/tasks/${id}`, {
        version,
      }),
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });

      const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
        queryKey: queryKeys.tasks.all,
      });
      const previousQueries = queries.map(([key, data]) => [key, data] as [readonly unknown[], unknown]);

      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Task>>>(
        { queryKey: queryKeys.tasks.all },
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            pages: oldData.pages.map((page) => ({
              ...page,
              items: page.items.filter((item) => item.id !== id),
            })),
          };
        }
      );

      return { previousQueries };
    },
    onError: (_err, _vars, context) => {
      context?.previousQueries.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Composite hook for tasks list with filtering and optimistic mutations.
 */
export function useTasks(filters?: {
  status?: string;
  priority?: string;
  project?: string;
  search?: string;
}) {
  const queryClient = useQueryClient();
  const { tasks: serverTasks, isLoading, refetch } = useTasksList({ limit: 200 });
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const moveTaskMutation = useMoveTask();
  const completeTaskMutation = useCompleteTask();
  const deleteTaskMutation = useDeleteTask();
  const updateTaskMutation = useUpdateTask();

  React.useEffect(() => {
    if (serverTasks) {
      setTasks(serverTasks);
    }
  }, [serverTasks]);

  const filteredTasks = React.useMemo(() => {
    const list = tasks.length > 0 ? tasks : serverTasks;
    return list.filter((task) => {
      if (filters?.status && filters.status !== 'all' && task.status !== filters.status) return false;
      if (filters?.priority && filters.priority !== 'all' && task.priority !== filters.priority) return false;
      if (filters?.project && filters.project !== 'all') {
        const projFilter = filters.project.toLowerCase().replace(/^#/, '');
        const matchName = task.project?.name?.toLowerCase() === projFilter;
        const matchId = task.project_id === filters.project;
        const matchTag = task.tags?.some((tag) => tag.toLowerCase().replace(/^#/, '') === projFilter);
        if (!matchName && !matchId && !matchTag) return false;
      }
      if (filters?.search) {
        const q = filters.search.toLowerCase();
        return (
          task.title.toLowerCase().includes(q) ||
          Boolean(task.description_markdown && task.description_markdown.toLowerCase().includes(q)) ||
          Boolean(task.description && task.description.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [tasks, serverTasks, filters]);

  const getTaskVersion = React.useCallback(
    (taskId: string): number => {
      const fromLocal = tasks.find((t) => t.id === taskId);
      if (fromLocal?.version) return fromLocal.version;
      const fromServer = serverTasks.find((t) => t.id === taskId);
      if (fromServer?.version) return fromServer.version;
      const fromCache = queryClient.getQueryData<Task>(queryKeys.tasks.detail(taskId));
      if (fromCache?.version) return fromCache.version;
      return 1;
    },
    [tasks, serverTasks, queryClient]
  );

  const moveTask = React.useCallback(
    (taskId: string, targetStatus: TaskStatus | TaskStatusType, newIndex?: number) => {
      const currentVersion = getTaskVersion(taskId);

      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                status: targetStatus as TaskStatus,
                sort_order: newIndex !== undefined ? newIndex : t.sort_order,
                version: currentVersion + 1,
                updated_at: new Date().toISOString(),
              }
            : t
        )
      );
      moveTaskMutation.mutate({
        id: taskId,
        version: currentVersion,
        status: targetStatus as TaskStatus,
        sort_order: newIndex,
      });
    },
    [moveTaskMutation, getTaskVersion]
  );

  const completeTask = React.useCallback(
    (taskId: string) => {
      const currentTask = tasks.find((t) => t.id === taskId) || serverTasks.find((t) => t.id === taskId);
      const isCurrentlyDone = currentTask?.status === TaskStatus.DONE;
      const newStatus = isCurrentlyDone ? TaskStatus.TODO : TaskStatus.DONE;
      const currentVersion = getTaskVersion(taskId);

      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                status: newStatus,
                completed_at: isCurrentlyDone ? null : new Date().toISOString(),
                version: currentVersion + 1,
                updated_at: new Date().toISOString(),
              }
            : t
        )
      );
      completeTaskMutation.mutate({
        id: taskId,
        version: currentVersion,
        status: newStatus,
      });
    },
    [completeTaskMutation, getTaskVersion, tasks, serverTasks]
  );

  const deleteTask = React.useCallback(
    (taskId: string) => {
      const currentVersion = getTaskVersion(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      deleteTaskMutation.mutate({ id: taskId, version: currentVersion });
    },
    [deleteTaskMutation, getTaskVersion]
  );

  const updateTask = React.useCallback(
    (input: UpdateTaskInput) => {
      const currentVersion = input.version ?? getTaskVersion(input.id);

      setTasks((prev) =>
        prev.map((t) =>
          t.id === input.id
            ? {
                ...t,
                ...input,
                version: currentVersion + 1,
                updated_at: new Date().toISOString(),
              }
            : t
        )
      );
      return updateTaskMutation.mutateAsync({
        ...input,
        version: currentVersion,
      });
    },
    [updateTaskMutation, getTaskVersion]
  );

  return {
    tasks: filteredTasks,
    allTasks: tasks,
    isLoading,
    refetch,
    moveTask,
    completeTask,
    deleteTask,
    updateTask,
  };
}

export function useTaskMutations() {
  const queryClient = useQueryClient();
  const moveTaskMutation = useMoveTask();
  const completeTaskMutation = useCompleteTask();
  const deleteTaskMutation = useDeleteTask();

  const getTaskVersion = (taskId: string): number => {
    const detail = queryClient.getQueryData<Task>(queryKeys.tasks.detail(taskId));
    if (detail?.version) return detail.version;
    const queries = queryClient.getQueriesData<InfiniteData<PaginatedResponse<Task>>>({
      queryKey: queryKeys.tasks.all,
    });
    for (const [, data] of queries) {
      if (data?.pages) {
        for (const page of data.pages) {
          const found = page.items?.find((item) => item.id === taskId);
          if (found?.version) return found.version;
        }
      }
    }
    return 1;
  };

  return {
    moveTaskOptimistic: (params: { taskId: string; targetColumnOrTaskId: string }) => {
      const version = getTaskVersion(params.taskId);
      moveTaskMutation.mutate({
        id: params.taskId,
        version,
        status: params.targetColumnOrTaskId as TaskStatus,
      });
    },
    completeTask: (taskId: string, targetStatus?: TaskStatus) => {
      const version = getTaskVersion(taskId);
      completeTaskMutation.mutate({ id: taskId, version, status: targetStatus });
    },
    deleteTask: (taskId: string) => {
      const version = getTaskVersion(taskId);
      deleteTaskMutation.mutate({ id: taskId, version });
    },
  };
}

export function useTaskAttachments(taskId?: string) {
  return useQuery<TaskAttachment[], Error>({
    queryKey: ['tasks', taskId, 'attachments'],
    queryFn: () => apiRequest<TaskAttachment[]>('GET', `/tasks/${taskId}/attachments`),
    enabled: Boolean(taskId),
  });
}

export function useUploadTaskAttachment() {
  const queryClient = useQueryClient();
  return useMutation<TaskAttachment, Error, { taskId: string; file: File }>({
    mutationFn: ({ taskId, file }) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiRequest<TaskAttachment>('POST', `/tasks/${taskId}/attachments`, {
        body: formData as unknown as undefined,
      });
    },
    onSuccess: (_, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', taskId, 'attachments'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(taskId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: ['attachments'] });
    },
  });
}

export function useProjectAttachments(projectId?: string) {
  return useQuery<TaskAttachment[], Error>({
    queryKey: ['attachments', 'project', projectId],
    queryFn: () =>
      apiRequest<TaskAttachment[]>('GET', '/attachments', {
        params: projectId ? { project_id: projectId } : undefined,
      }),
    enabled: Boolean(projectId),
  });
}

export function useDeleteAttachment() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { attachmentId: string; taskId?: string; projectId?: string }>({
    mutationFn: ({ attachmentId }) =>
      apiRequest<void>('DELETE', `/attachments/${attachmentId}`),
    onSuccess: (_, { taskId, projectId }) => {
      if (taskId) {
        queryClient.invalidateQueries({ queryKey: ['tasks', taskId, 'attachments'] });
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(taskId) });
      }
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ['attachments', 'project', projectId] });
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: ['attachments'] });
    },
  });
}


