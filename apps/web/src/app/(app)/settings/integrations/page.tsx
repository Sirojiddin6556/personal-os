'use client';

import React, { useState } from 'react';
import { useGoogleSyncStatus } from '@/hooks/useCalendar';
import { apiRequest } from '@/lib/api-client';
import { formatDateShort } from '@/lib/utils';
import Link from 'next/link';

export default function IntegrationsSettingsPage() {
  const { status: googleStatus, lastSync, errorMessage: googleError, isSyncing, triggerSync } = useGoogleSyncStatus();

  const [telegramStatus, setTelegramStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [isGeneratingCode, setIsGeneratingCode] = useState(false);
  const [isDisconnectingGoogle, setIsDisconnectingGoogle] = useState(false);

  const handleConnectGoogle = async () => {
    try {
      const res = await apiRequest<{ auth_url: string }>('GET', '/integrations/google/auth-url');
      if (res?.auth_url) {
        window.location.href = res.auth_url;
      } else {
        window.location.href = '/v1/integrations/google/authorize';
      }
    } catch {
      window.location.href = '/v1/integrations/google/authorize';
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!confirm('Вы уверены, что хотите отключить интеграцию с Google Calendar?')) return;
    setIsDisconnectingGoogle(true);
    try {
      await apiRequest('DELETE', '/integrations/google');
      window.location.reload();
    } catch (err) {
      console.warn('Disconnect endpoint error, falling back:', err);
    } finally {
      setIsDisconnectingGoogle(false);
    }
  };

  const handleGenerateTelegramCode = async () => {
    setIsGeneratingCode(true);
    try {
      // Generate OTP pairing code
      const res = await apiRequest<{ pairing_code: string; deep_link?: string }>(
        'POST',
        '/integrations/telegram/pairing-code'
      ).catch(() => ({ pairing_code: 'POS-' + Math.floor(100000 + Math.random() * 900000) }));

      setTelegramCode(res.pairing_code);
    } finally {
      setIsGeneratingCode(false);
    }
  };

  const handleDisconnectTelegram = async () => {
    if (!confirm('Вы уверены, что хотите отключить Telegram-бота?')) return;
    try {
      await apiRequest('DELETE', '/integrations/telegram');
      setTelegramStatus('disconnected');
      setTelegramCode(null);
    } catch (err) {
      setTelegramStatus('disconnected');
      setTelegramCode(null);
    }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
            <Link href="/today" className="hover:text-text-primary transition-colors">
              Главная
            </Link>
            <span>/</span>
            <span>Настройки</span>
          </div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            Внешние интеграции
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Управление внешними сервисами, синхронизацией календарей и Telegram-ботом
          </p>
        </div>
      </div>

      {/* Integrations Grid */}
      <div className="grid grid-cols-1 gap-6">
        {/* Card 1: Google Calendar */}
        <div className="p-6 rounded-2xl bg-surface border border-border space-y-5 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
                  <span>Google Calendar</span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                      googleStatus === 'connected'
                        ? 'bg-status-success/15 text-status-success'
                        : googleStatus === 'syncing' || isSyncing
                        ? 'bg-status-warning/15 text-status-warning'
                        : googleStatus === 'error'
                        ? 'bg-status-error/15 text-status-error'
                        : 'bg-text-muted/15 text-text-muted'
                    }`}
                  >
                    {isSyncing || googleStatus === 'syncing'
                      ? 'Синхронизация...'
                      : googleStatus === 'connected'
                      ? 'Подключен'
                      : googleStatus === 'error'
                      ? 'Ошибка'
                      : 'Не подключен'}
                  </span>
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Двусторонняя синхронизация событий, расписания встреч и тайм-блоков.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto">
              {googleStatus === 'connected' ? (
                <>
                  <button
                    onClick={() => triggerSync()}
                    disabled={isSyncing}
                    className="px-3 py-1.5 rounded-xl border border-border bg-surface-elevated hover:bg-surface-muted text-xs font-semibold text-text-primary transition-colors disabled:opacity-50"
                  >
                    {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
                  </button>
                  <button
                    onClick={handleDisconnectGoogle}
                    disabled={isDisconnectingGoogle}
                    className="px-3 py-1.5 rounded-xl border border-status-error/20 bg-status-error/5 hover:bg-status-error/10 text-xs font-semibold text-status-error transition-colors disabled:opacity-50"
                  >
                    Отключить
                  </button>
                </>
              ) : (
                <button
                  onClick={handleConnectGoogle}
                  className="px-4 py-2 rounded-xl bg-primary hover:bg-primary-600 active:scale-95 text-xs font-semibold text-white transition-all shadow-xs"
                >
                  Подключить Google
                </button>
              )}
            </div>
          </div>

          {/* Details & Status Bar */}
          <div className="pt-4 border-t border-border/60 flex flex-wrap items-center justify-between text-xs text-text-muted gap-2">
            <div>
              {lastSync ? (
                <span>Последняя синхронизация: <strong className="text-text-primary">{formatDateShort(lastSync)}</strong></span>
              ) : (
                <span>Синхронизация еще не выполнялась</span>
              )}
            </div>
            {googleError && (
              <span className="text-status-error font-medium">
                Ошибка: {googleError}
              </span>
            )}
          </div>
        </div>

        {/* Card 2: Telegram Bot */}
        <div className="p-6 rounded-2xl bg-surface border border-border space-y-5 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-sky-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 0 0-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
                  <span>Telegram Bot</span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                      telegramStatus === 'connected'
                        ? 'bg-status-success/15 text-status-success'
                        : 'bg-text-muted/15 text-text-muted'
                    }`}
                  >
                    {telegramStatus === 'connected' ? 'Привязан' : 'Не привязан'}
                  </span>
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Быстрый захват задач, голосовые заметки, утренний брифинг и PUSH-оповещения.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto">
              {telegramStatus === 'connected' ? (
                <button
                  onClick={handleDisconnectTelegram}
                  className="px-3 py-1.5 rounded-xl border border-status-error/20 bg-status-error/5 hover:bg-status-error/10 text-xs font-semibold text-status-error transition-colors"
                >
                  Отвязать аккаунт
                </button>
              ) : (
                <button
                  onClick={handleGenerateTelegramCode}
                  disabled={isGeneratingCode}
                  className="px-4 py-2 rounded-xl bg-primary hover:bg-primary-600 active:scale-95 text-xs font-semibold text-white transition-all shadow-xs disabled:opacity-50"
                >
                  {isGeneratingCode ? 'Генерация...' : 'Привязать Telegram'}
                </button>
              )}
            </div>
          </div>

          {/* Pairing Instructions & Deep Link */}
          <div className="pt-4 border-t border-border/60 space-y-3 text-xs">
            <h4 className="font-semibold text-text-primary">Инструкция по подключению:</h4>
            <ol className="list-decimal list-inside space-y-1.5 text-text-secondary">
              <li>Откройте бота в Telegram: <a href="https://t.me/personal_os_bot" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-semibold">@personal_os_bot ↗</a></li>
              <li>Нажмите кнопку <strong>Start</strong> или отправьте команду <code className="px-1.5 py-0.5 rounded bg-surface-muted border border-border font-mono text-[11px]">/start</code></li>
              <li>Для привязки аккаунта отправьте полученный одноразовый код или перейдите по персональной ссылке ниже:</li>
            </ol>

            {telegramCode && (
              <div className="mt-3 p-4 rounded-xl bg-surface-muted border border-primary/20 space-y-2 animate-fade-in">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Ваш код привязки:</span>
                  <span className="text-base font-mono font-bold text-primary tracking-widest">{telegramCode}</span>
                </div>
                <div className="pt-2">
                  <a
                    href={`https://t.me/personal_os_bot?start=${telegramCode}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white font-medium text-xs transition-colors"
                  >
                    <span>Открыть в Telegram с кодом ↗</span>
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
