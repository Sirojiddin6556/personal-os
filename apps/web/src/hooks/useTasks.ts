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

/**
 * Composite hook for tasks list with filtering and optimistic mutations.
 */
const DEFAULT_INITIAL_TASKS: Task[] = [
  {
    id: 'task-1',
    title: 'Подготовить отчёт по квартальной выручке',
    description_markdown: 'Собрать данные из CRM и 1C, свести P&L в единый дашборд',
    status: TaskStatus.INBOX,
    priority: Priority.P2,
    due_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    project: { id: 'p-work', name: 'work', color: '#6366f1' },
    subtasks: [
      { id: 'sub-1', title: 'Экспорт из 1С', is_completed: true, sort_order: 1 },
      { id: 'sub-2', title: 'Сверка с банковскими выписками', is_completed: true, sort_order: 2 },
      { id: 'sub-3', title: 'Сборка P&L', is_completed: false, sort_order: 3 },
      { id: 'sub-4', title: 'Ревью финансового директора', is_completed: false, sort_order: 4 },
    ],
    sort_order: 1,
    tags: ['finance', 'quarterly'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'task-2',
    title: 'Запустить миграцию базы данных PostgreSQL 16',
    description_markdown: 'Проверить RLS политики и индексы полнотекстового поиска',
    status: TaskStatus.TODO,
    priority: Priority.P1,
    due_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    project: { id: 'p-infra', name: 'infra', color: '#ef4444' },
    subtasks: [
      { id: 'sub-5', title: 'Создать резервную копию pg_dump', is_completed: true, sort_order: 1 },
      { id: 'sub-6', title: 'Применить миграцию Alembic', is_completed: false, sort_order: 2 },
    ],
    sort_order: 1,
    tags: ['devops', 'db'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'task-3',
    title: 'Забронировать билеты на конференцию HighLoad++',
    description_markdown: 'Выбрать перелёт и гостиницу рядом с кластером Сколково',
    status: TaskStatus.SCHEDULED,
    priority: Priority.P3,
    due_at: new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
    project: { id: 'p-personal', name: 'personal', color: '#10b981' },
    subtasks: [],
    sort_order: 1,
    tags: ['travel', 'edu'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'task-4',
    title: 'Ревью архитектуры UI компонентов (PR #42)',
    description_markdown: 'Проверить ARIA роли, фокус-ринги и соответствие дизайн-токенам',
    status: TaskStatus.IN_PROGRESS,
    priority: Priority.P2,
    due_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
    project: { id: 'p-frontend', name: 'frontend', color: '#0ea5e9' },
    subtasks: [
      { id: 'sub-7', title: 'Проверка доступности axe-core', is_completed: true, sort_order: 1 },
      { id: 'sub-8', title: 'Проверка темной темы', is_completed: false, sort_order: 2 },
    ],
    sort_order: 1,
    tags: ['code-review', 'a11y'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'task-5',
    title: 'Ждать согласование бюджета от финотдела',
    description_markdown: 'Ожидается подтверждение счета на лицензии LLM',
    status: TaskStatus.WAITING,
    priority: Priority.P4,
    due_at: new Date(Date.now() + 72 * 3600 * 1000).toISOString(),
    project: { id: 'p-work', name: 'work', color: '#6366f1' },
    subtasks: [],
    sort_order: 1,
    tags: ['finance', 'external'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'task-6',
    title: 'Настройка Telegram Bot Webhook для Personal OS',
    description_markdown: 'Интеграция бота для быстрого ввода задач через голосовые сообщения',
    status: TaskStatus.DONE,
    priority: Priority.P3,
    due_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
    project: { id: 'p-bot', name: 'integration', color: '#8b5cf6' },
    subtasks: [{ id: 'sub-9', title: 'TLS сертификат и эндпоинт', is_completed: true, sort_order: 1 }],
    sort_order: 1,
    tags: ['telegram', 'api'],
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export function useTasks(filters?: {
  status?: string;
  priority?: string;
  project?: string;
  search?: string;
}) {
  const [tasks, setTasks] = React.useState<Task[]>(DEFAULT_INITIAL_TASKS);
  const moveTaskMutation = useMoveTask();
  const completeTaskMutation = useCompleteTask();

  const filteredTasks = React.useMemo(() => {
    return tasks.filter((task) => {
      if (filters?.status && filters.status !== 'all' && task.status !== filters.status) return false;
      if (filters?.priority && filters.priority !== 'all' && task.priority !== filters.priority) return false;
      if (filters?.project && filters.project !== 'all' && task.project?.name !== filters.project) return false;
      if (filters?.search) {
        const q = filters.search.toLowerCase();
        return (
          task.title.toLowerCase().includes(q) ||
          (task.description_markdown && task.description_markdown.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [tasks, filters]);

  const moveTask = React.useCallback(
    (taskId: string, targetStatus: TaskStatus | TaskStatusType, newIndex?: number) => {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                status: targetStatus as TaskStatus,
                sort_order: newIndex !== undefined ? newIndex : t.sort_order,
                updated_at: new Date().toISOString(),
              }
            : t
        )
      );
      // Background optimistic mutation
      moveTaskMutation.mutate({
        id: taskId,
        version: 1,
        status: targetStatus as TaskStatus,
        sort_order: newIndex,
      });
    },
    [moveTaskMutation]
  );

  const completeTask = React.useCallback(
    (taskId: string) => {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                status: t.status === TaskStatus.DONE ? TaskStatus.TODO : TaskStatus.DONE,
                completed_at: t.status === TaskStatus.DONE ? null : new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }
            : t
        )
      );
      completeTaskMutation.mutate({ id: taskId, version: 1 });
    },
    [completeTaskMutation]
  );

  return {
    tasks: filteredTasks,
    allTasks: tasks,
    moveTask,
    completeTask,
  };
}

export function useTaskMutations() {
  const moveTaskMutation = useMoveTask();
  const completeTaskMutation = useCompleteTask();

  return {
    moveTaskOptimistic: (params: { taskId: string; targetColumnOrTaskId: string }) => {
      moveTaskMutation.mutate({
        id: params.taskId,
        version: 1,
        status: params.targetColumnOrTaskId as TaskStatus,
      });
    },
    completeTask: (taskId: string) => {
      completeTaskMutation.mutate({ id: taskId, version: 1 });
    },
  };
}

