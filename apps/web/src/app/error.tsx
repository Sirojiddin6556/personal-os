'use client';

import React, { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled Next.js Application Error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background text-text-primary text-center">
      <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900 flex items-center justify-center mb-4 text-2xl font-bold text-rose-600 shadow-2xs">
        !
      </div>
      <h1 className="text-xl font-bold tracking-tight">Что-то пошло не так</h1>
      <p className="text-xs text-text-muted mt-2 max-w-sm">
        Произошла непредвиденная ошибка при обработке запроса. Попробуйте обновить страницу.
      </p>
      <div className="mt-6 flex items-center gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="px-4 py-2 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary-600 transition-colors shadow-xs"
        >
          Повторить попытку
        </button>
        <button
          type="button"
          onClick={() => (window.location.href = '/today')}
          className="px-4 py-2 rounded-xl bg-surface border border-border text-text-primary text-xs font-semibold hover:bg-surface-muted transition-colors shadow-2xs"
        >
          На главную
        </button>
      </div>
    </div>
  );
}
