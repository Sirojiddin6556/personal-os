/**
 * @file useNotes.ts
 * @description TanStack Query hooks for markdown note editing, auto-saving, and RAG semantic search.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { Note, NoteSearchResult, NoteUpdateInput } from '@/types/domain';

/**
 * Fetch a single note by ID.
 */
export function useNote(id: string) {
  const query = useQuery<Note, Error>({
    queryKey: queryKeys.notes.detail(id),
    queryFn: () => apiRequest<Note>('GET', `/knowledge/notes/${id}`),
    enabled: Boolean(id),
    staleTime: 1000 * 60, // 1 minute
  });

  return {
    note: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook for updating note content / title with optimistic cache updates.
 */
export function useUpdateNote(id: string) {
  const queryClient = useQueryClient();

  return useMutation<Note, Error, NoteUpdateInput>({
    mutationFn: (body: NoteUpdateInput) =>
      apiRequest<Note, NoteUpdateInput>('PATCH', `/knowledge/notes/${id}`, { body }),
    onSuccess: (updatedNote) => {
      queryClient.setQueryData(queryKeys.notes.detail(id), updatedNote);
      queryClient.invalidateQueries({ queryKey: queryKeys.notes.all });
    },
  });
}

/**
 * Fetch list of notes.
 */
export function useNotes(isPinned?: boolean) {
  const query = useQuery<Note[], Error>({
    queryKey: ['notes', 'list', isPinned],
    queryFn: () =>
      apiRequest<Note[]>('GET', '/knowledge/notes', {
        params: isPinned !== undefined ? { is_pinned: isPinned } : undefined,
      }),
    staleTime: 1000 * 30,
  });

  return {
    notes: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook for creating a new note.
 */
export function useCreateNote() {
  const queryClient = useQueryClient();

  return useMutation<Note, Error, { title: string; content_markdown?: string; is_pinned?: boolean }>({
    mutationFn: (body) =>
      apiRequest<Note, { title: string; content_markdown?: string; is_pinned?: boolean }>(
        'POST',
        '/knowledge/notes',
        { body }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}

/**
 * Hook for semantic/full-text RAG search across knowledge notes.
 */
export function useNoteSearch(query: string, limit = 10) {
  const searchQuery = useQuery<NoteSearchResult[], Error>({
    queryKey: ['notes', 'search', query, limit],
    queryFn: () =>
      apiRequest<NoteSearchResult[]>('GET', '/knowledge/search', {
        params: { q: query, limit },
      }),
    enabled: Boolean(query && query.trim().length > 0),
    staleTime: 1000 * 30,
  });

  return {
    results: searchQuery.data ?? [],
    isLoading: searchQuery.isLoading,
    isError: searchQuery.isError,
    error: searchQuery.error,
    refetch: searchQuery.refetch,
  };
}
