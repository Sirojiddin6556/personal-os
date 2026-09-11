'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  useConnectGitHub,
  useCreateProjectCommit,
  useDeleteProject,
  useGitHubRepos,
  useGitHubStatus,
  useImportGitHubRepo,
  useProjectCommits,
  useProjectContents,
  useProjectFile,
  useProjects,
  useSyncProjectIssues,
} from '@/hooks/useGitHub';
import { useCreateTask, useTasks } from '@/hooks/useTasks';
import { useUIStore } from '@/stores/ui-store';
import { Priority, Project, TaskPriority, TaskStatus } from '@/types/domain';
import { cn, formatDateShort } from '@/lib/utils';
import { apiRequest } from '@/lib/api-client';

export default function ProjectsPage() {
  const { data: projects = [], isLoading: isLoadingProjects, refetch: refetchProjects } = useProjects();
  const { data: githubStatus } = useGitHubStatus();
  const { data: githubRepos = [], isLoading: isLoadingRepos } = useGitHubRepos(githubStatus?.status === 'connected');
  const importRepoMutation = useImportGitHubRepo();
  const deleteProjectMutation = useDeleteProject();
  const syncIssuesMutation = useSyncProjectIssues();
  const createCommitMutation = useCreateProjectCommit();
  const createTaskMutation = useCreateTask();

  const { openQuickAdd } = useUIStore();
  const { tasks: allTasks, completeTask, deleteTask } = useTasks();

  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'files' | 'commits' | 'tasks'>('overview');
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [repoSearchQuery, setRepoSearchQuery] = useState('');
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectColor, setNewProjectColor] = useState('#3B82F6');

  // File tree & editor state
  const [currentFilePath, setCurrentFilePath] = useState('');
  const [selectedFileForEdit, setSelectedFileForEdit] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [commitMessage, setCommitMessage] = useState('');
  const [isCommitting, setIsCommitting] = useState(false);
  const [commitSuccess, setCommitSuccess] = useState<string | null>(null);

  // New task form inside project
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskPriority, setNewTaskPriority] = useState<Priority>(Priority.P3);

  const selectedProject = projects.find((p) => p.id === selectedProjectId) || (projects.length > 0 ? projects[0] : null);
  const activeProject = selectedProject;

  const { data: projectCommits = [], isLoading: isLoadingCommits, refetch: refetchCommits } = useProjectCommits(
    activeProject?.github_repo ? activeProject.id : undefined
  );
  const { data: projectFiles = [], isLoading: isLoadingFiles, refetch: refetchFiles } = useProjectContents(
    activeProject?.github_repo ? activeProject.id : undefined,
    currentFilePath
  );
  const { data: activeFileDetail, isLoading: isLoadingFileDetail } = useProjectFile(
    activeProject?.github_repo ? activeProject.id : undefined,
    selectedFileForEdit || undefined
  );

  React.useEffect(() => {
    if (activeFileDetail && activeFileDetail.content !== undefined) {
      setFileContent(activeFileDetail.content);
    }
  }, [activeFileDetail]);

  const handleImportRepo = async (repoFullName: string, repoName: string) => {
    try {
      await importRepoMutation.mutateAsync({
        repo_full_name: repoFullName,
        name: repoName,
      });
      setIsImportModalOpen(false);
      refetchProjects();
    } catch (err: any) {
      alert(err?.message || 'Ошибка импорта репозитория');
    }
  };

  const handleCreateCustomProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      await apiRequest('POST', '/projects', {
        body: {
          name: newProjectName.trim(),
          color: newProjectColor,
        },
      });
      setNewProjectName('');
      setIsCreatingProject(false);
      refetchProjects();
    } catch (err: any) {
      alert(err?.message || 'Ошибка создания проекта');
    }
  };

  const handleDeleteProject = async (projectId: string, name: string) => {
    if (!confirm(`Удалить проект "${name}"? Задачи проекта останутся без привязки.`)) return;
    try {
      await deleteProjectMutation.mutateAsync(projectId);
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null);
      }
    } catch (err: any) {
      alert(err?.message || 'Ошибка удаления проекта');
    }
  };

  const handleSyncIssues = async () => {
    if (!activeProject) return;
    try {
      const res = await syncIssuesMutation.mutateAsync(activeProject.id);
      alert(`Синхронизировано ${res.length} задач из GitHub Issues!`);
    } catch (err: any) {
      alert(err?.message || 'Ошибка синхронизации issues');
    }
  };

  const handleCreateCommit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !selectedFileForEdit || !commitMessage.trim()) return;
    setIsCommitting(true);
    setCommitSuccess(null);
    try {
      const res = await createCommitMutation.mutateAsync({
        projectId: activeProject.id,
        path: selectedFileForEdit,
        content: fileContent,
        commit_message: commitMessage.trim(),
        sha: activeFileDetail?.sha,
      });
      setCommitSuccess(`Коммит ${res.short_sha} успешно создан!`);
      setCommitMessage('');
      refetchCommits();
      refetchFiles();
    } catch (err: any) {
      alert(err?.message || 'Ошибка отправки коммита');
    } finally {
      setIsCommitting(false);
    }
  };

  const handleCreateProjectTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || !activeProject) return;
    try {
      await createTaskMutation.mutateAsync({
        title: newTaskTitle.trim(),
        project_id: activeProject.id,
        priority: newTaskPriority,
        status: TaskStatus.TODO,
      });
      setNewTaskTitle('');
    } catch (err: any) {
      alert(err?.message || 'Ошибка создания задачи');
    }
  };

  const projectTasks = allTasks.filter(
    (t) => t.project_id === activeProject?.id || t.project?.name === activeProject?.name
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2.5">
            <span>Проекты & GitHub</span>
            {githubStatus?.status === 'connected' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-status-success/15 text-status-success">
                <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
                GitHub подключен
              </span>
            )}
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Импорт репозиториев, управление ветками, редактирование кода, коммиты и задачи
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {githubStatus?.status === 'connected' ? (
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-xs font-bold hover:opacity-90 active:scale-95 transition-all shadow-xs"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
              <span>Импорт с GitHub</span>
            </button>
          ) : (
            <Link
              href="/settings/integrations"
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-primary/30 bg-primary/10 text-primary text-xs font-bold hover:bg-primary/15 transition-colors"
            >
              <span>Подключить GitHub в настройках ↗</span>
            </Link>
          )}

          <button
            onClick={() => setIsCreatingProject(!isCreatingProject)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-primary text-white text-xs font-bold hover:bg-primary-600 active:scale-95 transition-all shadow-xs"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Новый проект</span>
          </button>
        </div>
      </div>

      {/* Inline Create Project Form */}
      {isCreatingProject && (
        <form onSubmit={handleCreateCustomProject} className="p-4 rounded-2xl bg-surface border border-border space-y-3 shadow-sm animate-fade-in">
          <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">Создание локального проекта</h3>
          <div className="flex flex-wrap gap-3">
            <input
              type="text"
              placeholder="Название проекта (например, backend-core)"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              required
              className="flex-1 min-w-[220px] px-3 py-1.5 text-xs bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <input
              type="color"
              value={newProjectColor}
              onChange={(e) => setNewProjectColor(e.target.value)}
              title="Цвет проекта"
              className="w-9 h-8 p-0.5 rounded-xl border border-border bg-surface-muted cursor-pointer"
            />
            <button
              type="submit"
              className="px-4 py-1.5 rounded-xl bg-primary text-white text-xs font-bold hover:bg-primary-600 transition-colors"
            >
              Создать
            </button>
            <button
              type="button"
              onClick={() => setIsCreatingProject(false)}
              className="px-3 py-1.5 rounded-xl border border-border text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {/* Main Grid: Projects Sidebar & Project Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* Left Column: Projects List (4 cols) */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Ваши проекты ({projects.length})
            </h2>
          </div>

          {isLoadingProjects ? (
            <div className="p-6 text-center text-xs text-text-muted">Загрузка проектов...</div>
          ) : projects.length === 0 ? (
            <div className="p-8 border border-dashed border-border rounded-2xl text-center space-y-2">
              <p className="text-sm font-semibold text-text-primary">Нет проектов</p>
              <p className="text-xs text-text-muted">
                Импортируйте репозиторий с GitHub или создайте проект вручную.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {projects.map((proj) => {
                const isSelected = (activeProject?.id === proj.id);
                const count = allTasks.filter((t) => t.project_id === proj.id || t.project?.name === proj.name).length;
                return (
                  <div
                    key={proj.id}
                    onClick={() => {
                      setSelectedProjectId(proj.id);
                      setSelectedFileForEdit(null);
                      setCurrentFilePath('');
                    }}
                    className={cn(
                      'group flex items-center justify-between p-3.5 rounded-2xl border cursor-pointer transition-all',
                      isSelected
                        ? 'bg-surface border-primary ring-1 ring-primary shadow-xs'
                        : 'bg-surface hover:bg-surface-muted border-border'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span
                        className="w-3 h-3 rounded-full shrink-0 shadow-xs"
                        style={{ backgroundColor: proj.color || '#3B82F6' }}
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-text-primary truncate">
                            {proj.name}
                          </span>
                          {proj.github_repo && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-text-secondary border border-border shrink-0">
                              GH
                            </span>
                          )}
                        </div>
                        {proj.github_repo ? (
                          <p className="text-[11px] font-mono text-text-muted truncate">
                            {proj.github_repo}
                          </p>
                        ) : (
                          <p className="text-[11px] text-text-muted truncate">
                            {proj.description || 'Локальный проект'}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-muted border border-border text-text-muted">
                        {count} зад.
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteProject(proj.id, proj.name);
                        }}
                        aria-label={`Удалить проект ${proj.name}`}
                        title="Удалить проект"
                        className="opacity-0 group-hover:opacity-100 p-1 text-text-muted hover:text-rose-600 rounded transition-opacity"
                      >
                        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Project Details & Workspace (8 cols) */}
        <div className="lg:col-span-8">
          {activeProject ? (
            <div className="bg-surface border border-border rounded-2xl shadow-xs overflow-hidden flex flex-col h-full">
              {/* Project Header Bar */}
              <div className="p-5 border-b border-border space-y-3 bg-surface-muted/50">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span
                      className="w-4 h-4 rounded-full shrink-0"
                      style={{ backgroundColor: activeProject.color || '#3B82F6' }}
                    />
                    <div>
                      <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
                        <span>{activeProject.name}</span>
                        {activeProject.github_repo && (
                          <a
                            href={`https://github.com/${activeProject.github_repo}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs font-mono font-medium text-primary hover:underline"
                          >
                            ({activeProject.github_repo} ↗)
                          </a>
                        )}
                      </h2>
                      {activeProject.description && (
                        <p className="text-xs text-text-secondary mt-0.5">{activeProject.description}</p>
                      )}
                    </div>
                  </div>

                  {activeProject.github_repo && (
                    <button
                      onClick={handleSyncIssues}
                      disabled={syncIssuesMutation.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border bg-surface hover:bg-surface-muted text-xs font-semibold text-text-primary transition-colors shrink-0 shadow-2xs"
                    >
                      <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                      </svg>
                      <span>{syncIssuesMutation.isPending ? 'Синхронизация...' : 'Импорт GitHub Issues'}</span>
                    </button>
                  )}
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-2 pt-2 border-t border-border/60">
                  <button
                    onClick={() => setActiveTab('overview')}
                    className={cn(
                      'px-3 py-1.5 text-xs font-bold rounded-lg transition-colors',
                      activeTab === 'overview'
                        ? 'bg-primary text-white shadow-xs'
                        : 'text-text-muted hover:text-text-primary hover:bg-surface'
                    )}
                  >
                    Обзор & Задачи ({projectTasks.length})
                  </button>

                  {activeProject.github_repo && (
                    <>
                      <button
                        onClick={() => setActiveTab('files')}
                        className={cn(
                          'px-3 py-1.5 text-xs font-bold rounded-lg transition-colors',
                          activeTab === 'files'
                            ? 'bg-primary text-white shadow-xs'
                            : 'text-text-muted hover:text-text-primary hover:bg-surface'
                        )}
                      >
                        Файлы & Код
                      </button>
                      <button
                        onClick={() => setActiveTab('commits')}
                        className={cn(
                          'px-3 py-1.5 text-xs font-bold rounded-lg transition-colors',
                          activeTab === 'commits'
                            ? 'bg-primary text-white shadow-xs'
                            : 'text-text-muted hover:text-text-primary hover:bg-surface'
                        )}
                      >
                        История коммитов ({projectCommits.length})
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Tab 1: Overview & Tasks */}
              {activeTab === 'overview' && (
                <div className="p-5 space-y-6 flex-1">
                  {/* Task Creation Form for this project */}
                  <form onSubmit={handleCreateProjectTask} className="p-4 rounded-2xl bg-surface-muted border border-border space-y-3">
                    <h3 className="text-xs font-bold text-text-primary uppercase tracking-wider">
                      Добавить задачу в проект «{activeProject.name}»
                    </h3>
                    <div className="flex flex-wrap gap-2.5">
                      <input
                        type="text"
                        placeholder="Что нужно сделать?"
                        value={newTaskTitle}
                        onChange={(e) => setNewTaskTitle(e.target.value)}
                        required
                        className="flex-1 min-w-[220px] px-3 py-2 text-xs bg-surface border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                      <select
                        value={newTaskPriority}
                        onChange={(e) => setNewTaskPriority(e.target.value as Priority)}
                        className="px-2.5 py-2 text-xs bg-surface border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value={Priority.P1}>🔴 P1 (Критический)</option>
                        <option value={Priority.P2}>🟠 P2 (Высокий)</option>
                        <option value={Priority.P3}>🔵 P3 (Средний)</option>
                        <option value={Priority.P4}>⚪ P4 (Низкий)</option>
                      </select>
                      <button
                        type="submit"
                        disabled={createTaskMutation.isPending || !newTaskTitle.trim()}
                        className="px-4 py-2 rounded-xl bg-primary hover:bg-primary-600 text-xs font-bold text-white transition-all shadow-xs disabled:opacity-50"
                      >
                        Добавить задачу
                      </button>
                    </div>
                  </form>

                  {/* Tasks List */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                        Задачи проекта ({projectTasks.length})
                      </h3>
                      <Link href="/tasks" className="text-xs font-semibold text-primary hover:underline">
                        Канбан-доска →
                      </Link>
                    </div>

                    {projectTasks.length === 0 ? (
                      <div className="p-8 border border-dashed border-border rounded-2xl text-center text-xs text-text-muted">
                        В этом проекте пока нет задач. Добавьте задачу выше или импортируйте GitHub Issues.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {projectTasks.map((t) => (
                          <div
                            key={t.id}
                            className="flex items-center justify-between p-3 rounded-xl bg-surface hover:bg-surface-muted/50 border border-border transition-colors"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <input
                                type="checkbox"
                                checked={t.status === 'done'}
                                onChange={() => completeTask(t.id)}
                                className="w-4 h-4 rounded border-border text-primary cursor-pointer shrink-0"
                              />
                              <span
                                className={cn(
                                  'text-xs font-medium text-text-primary truncate',
                                  t.status === 'done' && 'line-through text-text-muted'
                                )}
                              >
                                {t.title}
                              </span>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border bg-surface-muted text-text-secondary border-border">
                                {t.priority}
                              </span>
                              <button
                                onClick={() => deleteTask(t.id)}
                                title="Удалить задачу"
                                className="p-1 text-text-muted hover:text-rose-600 rounded transition-colors"
                              >
                                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="3 6 5 6 21 6" />
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                </svg>
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Files & Code Editor */}
              {activeTab === 'files' && activeProject.github_repo && (
                <div className="p-5 grid grid-cols-1 md:grid-cols-12 gap-4 flex-1">
                  {/* File Tree (4 cols) */}
                  <div className="md:col-span-4 border border-border rounded-xl p-3 bg-surface-muted/40 flex flex-col h-[520px]">
                    <div className="flex items-center justify-between pb-2 mb-2 border-b border-border">
                      <span className="text-xs font-bold text-text-primary font-mono truncate">
                        /{currentFilePath || 'корень'}
                      </span>
                      {currentFilePath && (
                        <button
                          onClick={() => {
                            const parts = currentFilePath.split('/');
                            parts.pop();
                            setCurrentFilePath(parts.join('/'));
                          }}
                          className="text-[11px] font-bold text-primary hover:underline"
                        >
                          .. Наверх
                        </button>
                      )}
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-1 pr-1 font-mono text-xs">
                      {isLoadingFiles ? (
                        <div className="p-4 text-center text-text-muted">Загрузка файлов...</div>
                      ) : (
                        projectFiles.map((file) => (
                          <div
                            key={file.path}
                            onClick={() => {
                              if (file.type === 'dir') {
                                setCurrentFilePath(file.path);
                              } else {
                                setSelectedFileForEdit(file.path);
                              }
                            }}
                            className={cn(
                              'flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors',
                              selectedFileForEdit === file.path
                                ? 'bg-primary text-white font-bold'
                                : 'hover:bg-surface text-text-primary'
                            )}
                          >
                            <span>{file.type === 'dir' ? '📁' : '📄'}</span>
                            <span className="truncate">{file.name}</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Code Editor & Commit Form (8 cols) */}
                  <div className="md:col-span-8 flex flex-col h-[520px] border border-border rounded-xl overflow-hidden bg-surface">
                    {selectedFileForEdit ? (
                      <form onSubmit={handleCreateCommit} className="flex flex-col h-full">
                        {/* Editor Header */}
                        <div className="px-4 py-2.5 bg-surface-muted border-b border-border flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-text-primary">
                            Редактирование: {selectedFileForEdit}
                          </span>
                          <span className="text-[11px] font-mono text-text-muted">
                            SHA: {activeFileDetail?.sha ? activeFileDetail.sha.slice(0, 7) : 'новый'}
                          </span>
                        </div>

                        {/* Editor Body */}
                        <div className="flex-1 relative">
                          <textarea
                            value={fileContent}
                            onChange={(e) => setFileContent(e.target.value)}
                            disabled={isLoadingFileDetail}
                            className="w-full h-full p-4 font-mono text-xs bg-slate-950 text-slate-100 dark:bg-slate-900 dark:text-slate-100 border-none resize-none focus:outline-none"
                            placeholder="// Содержимое файла..."
                          />
                        </div>

                        {/* Commit Footer */}
                        <div className="p-3 bg-surface border-t border-border space-y-2">
                          {commitSuccess && (
                            <p className="text-xs text-status-success font-semibold">
                              ✓ {commitSuccess}
                            </p>
                          )}
                          <div className="flex gap-2">
                            <input
                              type="text"
                              placeholder="Сообщение коммита (например: fix: update config parameter)"
                              value={commitMessage}
                              onChange={(e) => setCommitMessage(e.target.value)}
                              required
                              className="flex-1 px-3 py-1.5 text-xs bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                            />
                            <button
                              type="submit"
                              disabled={isCommitting || !commitMessage.trim()}
                              className="px-4 py-1.5 rounded-xl bg-primary hover:bg-primary-600 text-xs font-bold text-white transition-all shadow-xs disabled:opacity-50 shrink-0"
                            >
                              {isCommitting ? 'Коммит...' : 'Сделать коммит'}
                            </button>
                          </div>
                        </div>
                      </form>
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-text-muted space-y-2">
                        <span className="text-3xl">💻</span>
                        <p className="text-sm font-semibold text-text-primary">Файл не выбран</p>
                        <p className="text-xs">
                          Выберите файл из списка слева, чтобы просмотреть его содержимое, внести правки и сделать коммит в GitHub.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 3: Git Commits History */}
              {activeTab === 'commits' && activeProject.github_repo && (
                <div className="p-5 flex-1 overflow-y-auto space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                      Недавние коммиты ({projectCommits.length})
                    </h3>
                  </div>

                  {isLoadingCommits ? (
                    <div className="p-6 text-center text-xs text-text-muted">Загрузка коммитов...</div>
                  ) : projectCommits.length === 0 ? (
                    <div className="p-8 border border-dashed border-border rounded-2xl text-center text-xs text-text-muted">
                      Коммиты не найдены.
                    </div>
                  ) : (
                    <div className="space-y-2 font-mono text-xs">
                      {projectCommits.map((c) => (
                        <div
                          key={c.sha}
                          className="flex items-start justify-between p-3.5 rounded-xl bg-surface-muted/40 hover:bg-surface-muted border border-border transition-colors gap-4"
                        >
                          <div className="space-y-1 min-w-0">
                            <p className="font-semibold text-text-primary text-xs truncate">
                              {c.message}
                            </p>
                            <p className="text-[11px] text-text-muted">
                              {c.author_name} · {formatDateShort(c.date)}
                            </p>
                          </div>
                          <a
                            href={c.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2 py-1 rounded bg-surface border border-border text-primary hover:underline font-bold text-[11px] shrink-0"
                          >
                            {c.short_sha} ↗
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="h-full border border-dashed border-border rounded-2xl flex flex-col items-center justify-center p-12 text-center text-text-muted space-y-2">
              <span className="text-3xl">📂</span>
              <p className="text-sm font-semibold text-text-primary">Проект не выбран</p>
              <p className="text-xs">Выберите проект из списка слева или создайте новый.</p>
            </div>
          )}
        </div>
      </div>

      {/* GitHub Repository Import Modal */}
      {isImportModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-2xl shadow-2xl max-w-xl w-full p-6 space-y-5 max-h-[85vh] flex flex-col animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h3 className="text-lg font-bold text-text-primary flex items-center gap-2">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                <span>Импорт репозитория с GitHub</span>
              </h3>
              <button
                onClick={() => setIsImportModalOpen(false)}
                className="p-1.5 text-text-muted hover:text-text-primary rounded-lg"
              >
                ✕
              </button>
            </div>

            {/* Search filter */}
            <input
              type="text"
              placeholder="Поиск по названию репозитория..."
              value={repoSearchQuery}
              onChange={(e) => setRepoSearchQuery(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />

            {/* Repos List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {isLoadingRepos ? (
                <div className="p-8 text-center text-xs text-text-muted">Загрузка ваших репозиториев...</div>
              ) : (
                githubRepos
                  .filter((r) => r.full_name.toLowerCase().includes(repoSearchQuery.toLowerCase()))
                  .map((repo) => (
                    <div
                      key={repo.id}
                      className="p-3.5 rounded-xl border border-border bg-surface hover:bg-surface-muted/60 flex items-center justify-between gap-4 transition-colors"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-text-primary truncate">
                            {repo.name}
                          </span>
                          {repo.private && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold">
                              Private
                            </span>
                          )}
                          {repo.language && (
                            <span className="text-[10px] text-text-muted font-mono">
                              · {repo.language}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-text-muted font-mono truncate">{repo.full_name}</p>
                        {repo.description && (
                          <p className="text-xs text-text-secondary truncate mt-0.5">{repo.description}</p>
                        )}
                      </div>

                      <button
                        onClick={() => handleImportRepo(repo.full_name, repo.name)}
                        disabled={importRepoMutation.isPending}
                        className="px-3.5 py-1.5 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary-600 transition-colors shrink-0 shadow-xs disabled:opacity-50"
                      >
                        {importRepoMutation.isPending ? 'Импорт...' : 'Импортировать'}
                      </button>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
