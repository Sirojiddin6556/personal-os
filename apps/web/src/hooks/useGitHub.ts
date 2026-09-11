/**
 * @file useGitHub.ts
 * @description TanStack Query hooks for GitHub integration, repo import, commit management, and project sync.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { Project } from '@/types/domain';

export interface GitHubUser {
  login: string;
  name?: string;
  avatar_url?: string;
  html_url?: string;
  public_repos?: number;
}

export interface GitHubStatus {
  status: 'connected' | 'disconnected';
  user: GitHubUser | null;
  last_synced_at?: string | null;
  sync_error?: string | null;
}

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  private: boolean;
  html_url: string;
  default_branch: string;
  language: string | null;
  stargazers_count: number;
  updated_at: string;
}

export interface GitCommit {
  sha: string;
  short_sha: string;
  message: string;
  author_name: string;
  author_email: string;
  date: string;
  html_url: string;
}

export interface GitFileItem {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size: number;
  sha: string;
  html_url: string;
}

export interface GitFileDetail {
  name: string;
  path: string;
  sha: string;
  size: number;
  content: string;
  html_url: string;
}

export function useGitHubStatus() {
  return useQuery<GitHubStatus>({
    queryKey: ['integrations', 'github', 'status'],
    queryFn: () => apiRequest<GitHubStatus>('GET', '/integrations/github/status'),
    staleTime: 30000,
  });
}

export function useConnectGitHub() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; user: GitHubUser }, Error, { token: string }>({
    mutationFn: ({ token }) =>
      apiRequest('POST', '/integrations/github/connect', {
        body: { token },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'github'] });
    },
  });
}

export function useDisconnectGitHub() {
  const queryClient = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () => apiRequest('DELETE', '/integrations/github'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'github'] });
    },
  });
}

export function useGitHubRepos(enabled = true) {
  return useQuery<GitHubRepo[]>({
    queryKey: ['integrations', 'github', 'repos'],
    queryFn: () => apiRequest<GitHubRepo[]>('GET', '/integrations/github/repos'),
    enabled,
    staleTime: 60000,
  });
}

export function useImportGitHubRepo() {
  const queryClient = useQueryClient();
  return useMutation<Project, Error, { repo_full_name: string; name?: string; color?: string }>({
    mutationFn: (body) =>
      apiRequest<Project>('POST', '/integrations/github/import', {
        body,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => apiRequest<Project[]>('GET', '/projects'),
    staleTime: 30000,
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (projectId) => apiRequest('DELETE', `/projects/${projectId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useProjectCommits(projectId?: string, branch?: string) {
  return useQuery<GitCommit[]>({
    queryKey: ['integrations', 'github', 'projects', projectId, 'commits', branch],
    queryFn: () =>
      apiRequest<GitCommit[]>('GET', `/integrations/github/projects/${projectId}/commits`, {
        params: branch ? { branch } : undefined,
      }),
    enabled: Boolean(projectId),
    staleTime: 15000,
  });
}

export function useProjectContents(projectId?: string, path = '', ref?: string) {
  return useQuery<GitFileItem[]>({
    queryKey: ['integrations', 'github', 'projects', projectId, 'contents', path, ref],
    queryFn: () =>
      apiRequest<GitFileItem[]>('GET', `/integrations/github/projects/${projectId}/contents`, {
        params: { path, ...(ref ? { ref } : {}) },
      }),
    enabled: Boolean(projectId),
    staleTime: 15000,
  });
}

export function useProjectFile(projectId?: string, path?: string, ref?: string) {
  return useQuery<GitFileDetail>({
    queryKey: ['integrations', 'github', 'projects', projectId, 'file', path, ref],
    queryFn: () =>
      apiRequest<GitFileDetail>('GET', `/integrations/github/projects/${projectId}/file`, {
        params: { path: path || '', ...(ref ? { ref } : {}) },
      }),
    enabled: Boolean(projectId && path),
    staleTime: 10000,
  });
}

export function useCreateProjectCommit() {
  const queryClient = useQueryClient();
  return useMutation<
    { success: boolean; commit_sha: string; short_sha: string; message: string; html_url?: string },
    Error,
    { projectId: string; path: string; content: string; commit_message: string; branch?: string; sha?: string }
  >({
    mutationFn: ({ projectId, ...body }) =>
      apiRequest('POST', `/integrations/github/projects/${projectId}/commit`, {
        body,
      }),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'github', 'projects', projectId] });
    },
  });
}

export function useSyncProjectIssues() {
  const queryClient = useQueryClient();
  return useMutation<{ id: string; title: string }[], Error, string>({
    mutationFn: (projectId) =>
      apiRequest('POST', `/integrations/github/projects/${projectId}/sync-issues`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}
