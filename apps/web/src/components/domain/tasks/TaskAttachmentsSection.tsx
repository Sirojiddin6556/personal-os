'use client';

import React, { useRef, useState } from 'react';
import {
  useTaskAttachments,
  useUploadTaskAttachment,
  useDeleteAttachment,
} from '@/hooks/useTasks';
import { API_BASE_URL } from '@/lib/api-client';

function formatFileSize(bytes: number): string {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface TaskAttachmentsSectionProps {
  taskId: string;
}

export function TaskAttachmentsSection({ taskId }: TaskAttachmentsSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: attachments = [] } = useTaskAttachments(taskId);
  const uploadAttachmentMutation = useUploadTaskAttachment();
  const deleteAttachmentMutation = useDeleteAttachment();

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      for (let i = 0; i < files.length; i++) {
        await uploadAttachmentMutation.mutateAsync({
          taskId,
          file: files[i],
        });
      }
    } catch (err: any) {
      setUploadError(err?.message || 'Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          <span>Вложения ({attachments.length})</span>
        </label>

        <button
          type="button"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-surface-muted hover:bg-surface border border-border text-text-primary rounded-lg transition-colors cursor-pointer disabled:opacity-50"
        >
          {isUploading ? (
            <>
              <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10" strokeWidth="3" className="opacity-25" />
                <path d="M4 12a8 8 0 018-8" strokeWidth="3" className="opacity-75" />
              </svg>
              <span>Загрузка…</span>
            </>
          ) : (
            <span>+ Прикрепить файл</span>
          )}
        </button>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="hidden"
          multiple
        />
      </div>

      {uploadError && (
        <div className="mb-2 p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-600 dark:text-rose-400">
          {uploadError}
        </div>
      )}

      {attachments.length > 0 ? (
        <div className="space-y-1.5">
          {attachments.map((att) => (
            <div
              key={att.id}
              className="flex items-center justify-between gap-2 p-2 rounded-lg bg-surface-muted border border-border text-xs group hover:bg-surface transition-colors"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <svg className="w-4 h-4 text-text-muted shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <div className="min-w-0 flex-1">
                  <a
                    href={`${API_BASE_URL}/attachments/${att.id}/download`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-text-primary hover:text-primary truncate block hover:underline"
                    title={att.filename}
                  >
                    {att.filename}
                  </a>
                  <span className="text-[10px] text-text-muted">
                    {formatFileSize(att.file_size)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <a
                  href={`${API_BASE_URL}/attachments/${att.id}/download`}
                  download={att.filename}
                  className="p-1 text-text-muted hover:text-primary rounded hover:bg-surface-muted transition-colors"
                  title="Скачать файл"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </a>
                <button
                  type="button"
                  onClick={async () => {
                    if (window.confirm(`Удалить вложение "${att.filename}"?`)) {
                      await deleteAttachmentMutation.mutateAsync({
                        attachmentId: att.id,
                        taskId,
                      });
                    }
                  }}
                  className="p-1 text-text-muted hover:text-rose-500 rounded hover:bg-surface-muted transition-colors"
                  title="Удалить файл"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="p-3 border-2 border-dashed border-border hover:border-primary/50 rounded-xl text-center cursor-pointer transition-colors bg-surface-muted/50 hover:bg-surface-muted"
        >
          <svg className="w-4 h-4 mx-auto mb-1 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          <p className="text-xs text-text-muted">
            Нажмите, чтобы прикрепить файлы
          </p>
          <p className="text-[10px] text-text-muted/70 mt-0.5">
            До 50 МБ (документы, скриншоты, дампы)
          </p>
        </div>
      )}
    </div>
  );
}
