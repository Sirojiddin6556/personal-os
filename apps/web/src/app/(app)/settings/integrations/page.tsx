'use client';

import React, { useState } from 'react';
import { useGoogleSyncStatus } from '@/hooks/useCalendar';
import {
  useConnectGitHub,
  useDisconnectGitHub,
  useGitHubStatus,
} from '@/hooks/useGitHub';
import { apiRequest } from '@/lib/api-client';
import { formatDateShort } from '@/lib/utils';
import Link from 'next/link';

export default function IntegrationsSettingsPage() {
  const { status: googleStatus, lastSync, errorMessage: googleError, isSyncing, triggerSync } = useGoogleSyncStatus();
  const { data: githubData, isLoading: isLoadingGithub } = useGitHubStatus();
  const connectGitHubMutation = useConnectGitHub();
  const disconnectGitHubMutation = useDisconnectGitHub();

  const [githubToken, setGithubToken] = useState('');
  const [isConnectingGithub, setIsConnectingGithub] = useState(false);
  const [githubError, setGithubError] = useState<string | null>(null);

  const [telegramStatus, setTelegramStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [isGeneratingCode, setIsGeneratingCode] = useState(false);
  const [isDisconnectingGoogle, setIsDisconnectingGoogle] = useState(false);

  const handleConnectGitHub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubToken.trim()) return;
    setIsConnectingGithub(true);
    setGithubError(null);
    try {
      await connectGitHubMutation.mutateAsync({ token: githubToken.trim() });
      setGithubToken('');
    } catch (err: any) {
      setGithubError(err?.message || 'Не удалось подключить GitHub. Проверьте правильность токена.');
    } finally {
      setIsConnectingGithub(false);
    }
  };

  const handleDisconnectGitHub = async () => {
    if (!confirm('Вы уверены, что хотите отключить интеграцию с GitHub?')) return;
    try {
      await disconnectGitHubMutation.mutateAsync();
    } catch (err: any) {
      alert(err?.message || 'Ошибка при отключении GitHub');
    }
  };

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
        {/* Card 0: GitHub Integration */}
        <div className="p-6 rounded-2xl bg-surface border border-border space-y-5 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-slate-900/10 dark:bg-white/10 border border-border flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-text-primary" viewBox="0 0 24 24" fill="currentColor">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
                  <span>GitHub</span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                      githubData?.status === 'connected'
                        ? 'bg-status-success/15 text-status-success'
                        : 'bg-text-muted/15 text-text-muted'
                    }`}
                  >
                    {isLoadingGithub
                      ? 'Проверка...'
                      : githubData?.status === 'connected'
                      ? 'Подключен'
                      : 'Не подключен'}
                  </span>
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Импорт репозиториев, управление ветками, коммиты и задачи по проектам.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto">
              {githubData?.status === 'connected' ? (
                <>
                  <Link
                    href="/projects"
                    className="px-3.5 py-1.5 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary-600 transition-colors shadow-xs"
                  >
                    Перейти к проектам →
                  </Link>
                  <button
                    onClick={handleDisconnectGitHub}
                    className="px-3 py-1.5 rounded-xl border border-status-error/20 bg-status-error/5 hover:bg-status-error/10 text-xs font-semibold text-status-error transition-colors"
                  >
                    Отключить
                  </button>
                </>
              ) : null}
            </div>
          </div>

          {/* Connected User Details or Token Connection Form */}
          {githubData?.status === 'connected' && githubData.user ? (
            <div className="p-4 rounded-xl bg-surface-muted border border-border flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {githubData.user.avatar_url && (
                  <img
                    src={githubData.user.avatar_url}
                    alt={githubData.user.login}
                    className="w-10 h-10 rounded-full border border-border"
                  />
                )}
                <div>
                  <p className="text-sm font-bold text-text-primary">
                    {githubData.user.name || githubData.user.login}
                  </p>
                  <p className="text-xs text-text-muted font-mono">
                    @{githubData.user.login} · {githubData.user.public_repos ?? 0} репозиториев
                  </p>
                </div>
              </div>
              <a
                href={githubData.user.html_url || `https://github.com/${githubData.user.login}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium text-primary hover:underline"
              >
                Открыть профиль ↗
              </a>
            </div>
          ) : (
            <form onSubmit={handleConnectGitHub} className="pt-2 space-y-3">
              <div className="space-y-1.5">
                <label htmlFor="gh-token" className="block text-xs font-semibold text-text-primary">
                  Personal Access Token (classic или fine-grained):
                </label>
                <div className="flex gap-2">
                  <input
                    id="gh-token"
                    type="password"
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    required
                    className="flex-1 px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                  />
                  <button
                    type="submit"
                    disabled={isConnectingGithub || !githubToken.trim()}
                    className="px-4 py-2 rounded-xl bg-primary hover:bg-primary-600 active:scale-95 text-xs font-semibold text-white transition-all shadow-xs disabled:opacity-50 shrink-0"
                  >
                    {isConnectingGithub ? 'Подключение...' : 'Подключить'}
                  </button>
                </div>
                {githubError && (
                  <p className="text-xs text-rose-600 dark:text-rose-400 font-medium">
                    ⚠️ {githubError}
                  </p>
                )}
              </div>
              <p className="text-[11px] text-text-muted">
                💡 Создать токен с правами <code className="px-1 py-0.5 rounded bg-surface-muted border border-border font-mono">repo</code> можно в{' '}
                <a
                  href="https://github.com/settings/tokens/new?scopes=repo"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline font-medium"
                >
                  GitHub Settings → Developer Settings → Personal access tokens ↗
                </a>
              </p>
            </form>
          )}
        </div>

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
