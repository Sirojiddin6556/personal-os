'use client';

import React from 'react';
import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background text-text-primary text-center">
      <div className="w-16 h-16 rounded-2xl bg-surface-muted border border-border flex items-center justify-center mb-4 text-2xl font-bold shadow-2xs">
        404
      </div>
      <h1 className="text-xl font-bold tracking-tight">Страница не найдена</h1>
      <p className="text-xs text-text-muted mt-2 max-w-sm">
        Запрошенная страница или ресурс не существует либо был перемещён.
      </p>
      <Link
        href="/today"
        className="mt-6 px-4 py-2 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary-600 transition-colors shadow-xs"
      >
        Вернуться на главную
      </Link>
    </div>
  );
}
