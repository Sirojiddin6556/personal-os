'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { useUIStore } from '@/stores/ui-store';

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { openQuickAdd } = useUIStore();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Check token in localStorage or cookie
    const token = localStorage.getItem('personal_os_access_token');
    const hasCookie = document.cookie.includes('personal_os_access_token=');

    if (!token && !hasCookie) {
      // In production builds, bypass is strictly disabled.
      // In development or test builds, check for explicit bypass flag.
      const isProduction = process.env.NODE_ENV === 'production';
      const isTestOrDev =
        !isProduction &&
        (process.env.NODE_ENV === 'development' ||
          process.env.NEXT_PUBLIC_E2E_AUTH_BYPASS === 'true');

      const bypass =
        isTestOrDev && localStorage.getItem('personal_os_bypass_auth') === 'true';

      if (!bypass) {
        setIsAuthenticated(false);
        router.replace('/login');
        return;
      }
    }

    setIsAuthenticated(true);
  }, [router]);

  // Global Cmd+K / Ctrl+K shortcut for QuickAddModal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openQuickAdd();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [openQuickAdd]);

  // Loading state while checking authentication
  if (isAuthenticated === null) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background text-text-muted">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="text-xs font-medium">Проверка авторизации...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <AppShell>{children}</AppShell>;
}
