'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { apiRequest } from '@/lib/api-client';

type Step = 'disconnected' | 'code_sent' | 'password_needed' | 'connected' | 'error';

interface AccountStatus {
  status: Step;
  phone?: string | null;
  account?: string | null;
  error?: string | null;
  sources?: string[];
}

const SOURCE_TITLE: Record<string, string> = { humo: '@HumoCardBot', uzcard: '@CardXabarBot' };

const inputCls =
  'w-full text-xs px-3 py-2.5 bg-surface-muted border border-border rounded-xl text-text-primary focus:outline-none focus:ring-1 focus:ring-primary';
const btnCls =
  'px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold disabled:opacity-50 transition-colors';

/**
 * Opt-in: the server signs in to the user's own Telegram account (as an extra
 * device) and reads only @HumoCardBot / @CardXabarBot, so bank notices are
 * recorded without forwarding. Secrets go straight to the API and are stored
 * encrypted; nothing is kept in the browser.
 */
export function BankAccountReaderCard() {
  const [state, setState] = useState<AccountStatus>({ status: 'disconnected' });
  const [apiId, setApiId] = useState('');
  const [apiHash, setApiHash] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiRequest<AccountStatus>('GET', '/integrations/telegram-account/status')
      .then(setState)
      .catch(() => {});
  }, []);

  useEffect(load, [load]);

  const run = async (fn: () => Promise<AccountStatus>) => {
    setBusy(true);
    setError(null);
    try {
      setState(await fn());
      setCode('');
      setPassword('');
    } catch (err: any) {
      setError(err?.message || 'Не удалось выполнить действие');
    } finally {
      setBusy(false);
    }
  };

  const start = (e: React.FormEvent) => {
    e.preventDefault();
    run(() =>
      apiRequest<AccountStatus, { api_id: number; api_hash: string; phone: string }>(
        'POST',
        '/integrations/telegram-account/start',
        { body: { api_id: Number(apiId), api_hash: apiHash.trim(), phone } }
      )
    ).then(() => setApiHash(''));
  };

  const sendCode = (e: React.FormEvent) => {
    e.preventDefault();
    run(() =>
      apiRequest<AccountStatus, { code: string }>('POST', '/integrations/telegram-account/code', { body: { code } })
    );
  };

  const sendPassword = (e: React.FormEvent) => {
    e.preventDefault();
    run(() =>
      apiRequest<AccountStatus, { password: string }>('POST', '/integrations/telegram-account/password', {
        body: { password },
      })
    );
  };

  const disconnect = () =>
    run(() => apiRequest<AccountStatus>('DELETE', '/integrations/telegram-account'));

  const connected = state.status === 'connected';

  return (
    <div className="p-6 rounded-2xl bg-surface border border-border space-y-4 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-text-primary flex items-center gap-2 flex-wrap">
            <span>Автоматически читать уведомления банков</span>
            <span
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                connected ? 'bg-status-success/15 text-status-success' : 'bg-text-muted/15 text-text-muted'
              }`}
            >
              {connected ? 'Включено' : 'Выключено'}
            </span>
          </h3>
          <p className="text-xs text-text-muted mt-0.5">
            HUMO (@HumoCardBot) и Uzcard (@CardXabarBot) — без пересылки: сервер входит в ваш Telegram как
            отдельное устройство и читает только эти два чата.
          </p>
        </div>
        {connected && (
          <button onClick={disconnect} disabled={busy} className="text-xs font-semibold text-status-error hover:underline shrink-0">
            Отключить и завершить сеанс
          </button>
        )}
      </div>

      {connected && (
        <div className="text-xs text-text-secondary space-y-1">
          <p>
            Аккаунт: <b>{state.account || state.phone}</b>
          </p>
          <p>
            Источники:{' '}
            {state.sources && state.sources.length
              ? state.sources.map((s) => SOURCE_TITLE[s] || s).join(', ')
              : 'пока нет (начнутся после первого сообщения банка)'}
          </p>
          <p className="text-text-muted">
            Старые уведомления не загружаются — только новые. Категорию бот спросит в вашем чате с ним.
          </p>
        </div>
      )}

      {state.status === 'error' && state.error && (
        <p className="text-xs text-status-error font-medium">⚠️ {state.error}</p>
      )}

      {(state.status === 'disconnected' || state.status === 'error') && (
        <form onSubmit={start} className="space-y-3">
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-700 dark:text-amber-400 space-y-1">
            <p>
              <b>Важно:</b> у сервера будет полный доступ к вашему аккаунту Telegram (код читает только банковские
              чаты). Отключить можно здесь или в Telegram → Настройки → Устройства.
            </p>
            <p>
              api_id и api_hash — на{' '}
              <a href="https://my.telegram.org/apps" target="_blank" rel="noopener noreferrer" className="underline font-semibold">
                my.telegram.org/apps
              </a>
              . Никому их не пересылайте.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className={inputCls} inputMode="numeric" placeholder="api_id" value={apiId}
              onChange={(e) => setApiId(e.target.value.replace(/[^0-9]/g, ''))} required />
            <input className={inputCls} placeholder="api_hash" value={apiHash} autoComplete="off"
              onChange={(e) => setApiHash(e.target.value.trim())} required />
            <input className={inputCls} inputMode="tel" placeholder="+998 90 123 45 67" value={phone}
              onChange={(e) => setPhone(e.target.value)} required />
          </div>
          <button type="submit" disabled={busy || !apiId || apiHash.length !== 32 || !phone} className={btnCls}>
            {busy ? 'Отправка…' : 'Получить код'}
          </button>
        </form>
      )}

      {state.status === 'code_sent' && (
        <form onSubmit={sendCode} className="space-y-3">
          <p className="text-xs text-text-secondary">
            Код отправлен в Telegram на {state.phone} (служебный чат «Telegram»). Введите его здесь.
          </p>
          <div className="flex gap-2">
            <input className={inputCls} inputMode="numeric" autoComplete="one-time-code" placeholder="Код"
              value={code} onChange={(e) => setCode(e.target.value)} required />
            <button type="submit" disabled={busy || code.length < 4} className={btnCls}>
              {busy ? 'Проверка…' : 'Войти'}
            </button>
          </div>
          <button type="button" onClick={disconnect} className="text-[11px] text-text-muted hover:underline">
            Отменить
          </button>
        </form>
      )}

      {state.status === 'password_needed' && (
        <form onSubmit={sendPassword} className="space-y-3">
          <p className="text-xs text-text-secondary">
            У аккаунта включена двухэтапная проверка. Введите облачный пароль Telegram.
          </p>
          <div className="flex gap-2">
            <input className={inputCls} type="password" autoComplete="off" placeholder="Облачный пароль"
              value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="submit" disabled={busy || !password} className={btnCls}>
              {busy ? 'Проверка…' : 'Подтвердить'}
            </button>
          </div>
          <button type="button" onClick={disconnect} className="text-[11px] text-text-muted hover:underline">
            Отменить
          </button>
        </form>
      )}

      {error && <p className="text-xs text-status-error font-medium">⚠️ {error}</p>}
    </div>
  );
}
