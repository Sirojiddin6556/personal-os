'use client';

import React from 'react';

export default function AppLoading() {
  return (
    <div className="flex h-[calc(100vh-64px)] w-full items-center justify-center bg-background text-text-muted">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        <span className="text-xs font-medium">Загрузка данных...</span>
      </div>
    </div>
  );
}
