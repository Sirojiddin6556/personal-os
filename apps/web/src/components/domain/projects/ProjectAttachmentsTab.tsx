'use client';

import React, { useRef, useState } from 'react';
import { Task, TaskAttachment } from '@/types/domain';
import { useProjectAttachments, useDeleteAttachment } from '@/hooks/useTasks';
import { apiRequest, attachmentUrl, openAttachment } from '@/lib/api-client';
import { useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';

interface ProjectAttachmentsTabProps {
  projectId: string;
  projectName: string;
  projectTasks: Task[];
}

export function ProjectAttachmentsTab({
  projectId,
  projectName,
  projectTasks,
}: ProjectAttachmentsTabProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [targetTaskId, setTargetTaskId] = useState<string>('');

  const { data: serverAttachments = [], isLoading } = useProjectAttachments(projectId);
  const deleteMutation = useDeleteAttachment();

  // Combine server attachments with any attachments already present in project tasks
  const allAttachments = React.useMemo(() => {
    const map = new Map<string, TaskAttachment & { taskTitle?: string }>();

    // Add server-returned attachments
    serverAttachments.forEach((att) => {
      const task = projectTasks.find((t) => t.id === att.task_id);
      map.set(att.id, { ...att, taskTitle: task?.title });
    });

    // Add any task attachments from project tasks that might not have indexed yet
    projectTasks.forEach((task) => {
      (task.attachments || []).forEach((att) => {
        if (!map.has(att.id)) {
          map.set(att.id, { ...att, taskTitle: task.title });
        }
      });
    });

    return Array.from(map.values());
  }, [serverAttachments, projectTasks]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Upload either to selected task or default to first task
      const taskIdToUse = targetTaskId || (projectTasks.length > 0 ? projectTasks[0].id : null);
      if (!taskIdToUse) {
        throw new Error('Сначала создайте задачу в проекте для прикрепления файла');
      }

      await apiRequest('POST', `/tasks/${taskIdToUse}/attachments`, {
        body: formData as unknown as undefined,
      });

      queryClient.invalidateQueries({ queryKey: ['attachments'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      setUploadError(err?.message || 'Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (attId: string, filename: string) => {
    if (!confirm(`Удалить файл «${filename}»?`)) return;
    try {
      await deleteMutation.mutateAsync({ attachmentId: attId, projectId });
    } catch (err: any) {
      alert(err?.message || 'Не удалось удалить файл');
    }
  };

  return (
    <div className="p-5 space-y-6 flex-1">
      {/* Upload Box */}
      <div className="p-5 rounded-2xl bg-surface-muted border border-border space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-text-primary">
              Файлы и вложения проекта «{projectName}»
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              Технические задания, спецификации, документы и архивы
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
            />
            {projectTasks.length > 1 && (
              <select
                value={targetTaskId}
                onChange={(e) => setTargetTaskId(e.target.value)}
                className="text-xs bg-surface border border-border rounded-xl px-2.5 py-1.5 text-text-primary focus:outline-none"
              >
                <option value="">Прикрепить к первой задаче</option>
                {projectTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-primary hover:bg-primary-600 text-white text-xs font-bold transition-all shadow-xs disabled:opacity-50"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>{isUploading ? 'Загрузка...' : 'Загрузить файл'}</span>
            </button>
          </div>
        </div>

        {uploadError && (
          <div className="p-3 text-xs text-rose-600 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 rounded-xl">
            {uploadError}
          </div>
        )}
      </div>

      {/* Files List */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-text-muted">
          Прикрепленные файлы ({allAttachments.length})
        </h4>

        {isLoading ? (
          <div className="p-8 text-center text-xs text-text-muted">Загрузка файлов...</div>
        ) : allAttachments.length === 0 ? (
          <div className="p-8 border border-dashed border-border rounded-2xl text-center text-xs text-text-muted">
            В этом проекте пока нет прикрепленных файлов.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {allAttachments.map((att) => {
              const isPdf = att.filename.toLowerCase().endsWith('.pdf');
              const isWord =
                att.filename.toLowerCase().endsWith('.docx') ||
                att.filename.toLowerCase().endsWith('.doc');

              return (
                <div
                  key={att.id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-surface border border-border hover:border-primary/40 shadow-2xs hover:shadow-xs transition-all"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={cn(
                        'w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs uppercase shrink-0',
                        isPdf
                          ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                          : isWord
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                          : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                      )}
                    >
                      {isPdf ? 'PDF' : isWord ? 'DOCX' : 'FILE'}
                    </div>

                    <div className="min-w-0">
                      <a
                        href={attachmentUrl(att.id)}
                        onClick={(e) => void openAttachment(e, att.id, att.filename)}
                        target="_blank"
                        rel="noopener noreferrer"
                        download={att.filename}
                        className="text-xs font-semibold text-text-primary hover:text-primary transition-colors truncate block"
                        title={att.filename}
                      >
                        {att.filename}
                      </a>
                      <div className="flex items-center gap-2 text-[11px] text-text-muted mt-0.5">
                        <span>{(att.file_size / (1024 * 1024)).toFixed(2)} MB</span>
                        {att.taskTitle && (
                          <>
                            <span>•</span>
                            <span className="truncate max-w-[180px]" title={att.taskTitle}>
                              {att.taskTitle}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <a
                      href={attachmentUrl(att.id)}
                      onClick={(e) => void openAttachment(e, att.id, att.filename)}
                      target="_blank"
                      rel="noopener noreferrer"
                      download={att.filename}
                      className="p-2 text-text-muted hover:text-primary hover:bg-surface-muted rounded-lg transition-colors"
                      title="Скачать"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                    </a>
                    <button
                      type="button"
                      onClick={() => handleDelete(att.id, att.filename)}
                      className="p-2 text-text-muted hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-lg transition-colors"
                      title="Удалить"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
    </div>
  );
}
