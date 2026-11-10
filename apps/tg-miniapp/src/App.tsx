import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import { IconCalendar, IconPlus, IconSun, IconTasks, IconWallet, ToastProvider } from './components/ui';
import { api, ApiError, setSession, setUnauthorizedHandler } from './lib/api';
import { haptic, insideTelegram, tg } from './lib/telegram';
import type { AIPlan, Task, TelegramAuthResponse } from './lib/types';
import { FinanceScreen } from './screens/Finance';
import { LoginScreen } from './screens/Login';
import { PlannerScreen } from './screens/Planner';
import { TasksScreen } from './screens/Tasks';
import { TodayScreen } from './screens/Today';
import { PlanPreviewSheet } from './sheets/PlanPreview';
import { QuickAddSheet } from './sheets/QuickAdd';
import { TaskDetailSheet } from './sheets/TaskDetail';

type Auth =
  | { state: 'loading' }
  | { state: 'link'; telegramName?: string }
  | { state: 'browser' }
  | { state: 'fatal'; message: string }
  | { state: 'ready'; name: string };

type Tab = 'today' | 'tasks' | 'finance' | 'planner';
type SheetState =
  | { kind: 'none' }
  | { kind: 'add'; prefill: string }
  | { kind: 'task'; id: string }
  | { kind: 'plan'; plan: AIPlan };

const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function App() {
  const qc = useQueryClient();
  const [auth, setAuth] = useState<Auth>({ state: 'loading' });
  const [busy, setBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const finishLogin = useCallback((token: string, workspaceId: string, fullName: string, tgName?: string | null) => {
    setSession({ token, workspaceId, fullName });
    qc.clear();
    setAuth({ state: 'ready', name: tgName || fullName.split(' ')[0] || 'друг' });
  }, [qc]);

  const telegramLogin = useCallback(async () => {
    setAuth({ state: 'loading' });
    try {
      const r = await api<TelegramAuthResponse>('/auth/telegram', { body: { init_data: tg!.initData }, anonymous: true });
      finishLogin(r.access_token, r.workspace_id, r.user.full_name, r.telegram_user.first_name);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'TELEGRAM_NOT_LINKED') {
        setAuth({ state: 'link', telegramName: tg?.initDataUnsafe.user?.first_name });
      } else {
        setAuth({ state: 'fatal', message: errorText(e) });
      }
    }
  }, [finishLogin]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSession(null);
      if (insideTelegram) void telegramLogin(); // token expired -> silently re-auth
      else setAuth({ state: 'browser' });
    });
    if (insideTelegram) void telegramLogin();
    else setAuth({ state: 'browser' });
  }, [telegramLogin]);

  const submitLogin = async (email: string, password: string) => {
    setBusy(true);
    setLoginError(null);
    try {
      if (auth.state === 'link') {
        const r = await api<TelegramAuthResponse>('/auth/telegram/link', {
          body: { init_data: tg!.initData, email, password },
          anonymous: true,
        });
        haptic.success();
        finishLogin(r.access_token, r.workspace_id, r.user.full_name, r.telegram_user.first_name);
      } else {
        const t = await api<{ access_token: string }>('/auth/login', { body: { email, password }, anonymous: true });
        setSession({ token: t.access_token, workspaceId: '', fullName: '' });
        const [me, workspaces] = await Promise.all([
          api<{ full_name: string }>('/auth/me'),
          api<Array<{ id: string }>>('/workspaces'),
        ]);
        if (!workspaces.length) throw new Error('У аккаунта нет рабочего пространства');
        finishLogin(t.access_token, workspaces[0].id, me.full_name);
      }
    } catch (e) {
      haptic.error();
      setSession(null);
      setLoginError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (auth.state === 'loading') {
    return <div className="center-screen" style={{ justifyContent: 'center', alignItems: 'center' }}><span className="muted">Загрузка…</span></div>;
  }
  if (auth.state === 'fatal') {
    return (
      <div className="center-screen" style={{ justifyContent: 'center' }}>
        <div className="error-box" role="alert">Не удалось войти: {auth.message}</div>
        <button type="button" className="btn block" onClick={() => void telegramLogin()}>Повторить</button>
      </div>
    );
  }
  if (auth.state === 'link' || auth.state === 'browser') {
    return (
      <LoginScreen
        mode={auth.state}
        telegramName={auth.state === 'link' ? auth.telegramName : undefined}
        busy={busy}
        error={loginError}
        onSubmit={submitLogin}
      />
    );
  }
  return <Shell name={auth.name} />;
}

function Shell({ name }: { name: string }) {
  const [tab, setTab] = useState<Tab>('today');
  const [sheet, setSheet] = useState<SheetState>({ kind: 'none' });
  const close = useCallback(() => setSheet({ kind: 'none' }), []);
  const openTask = useCallback((t: Task) => setSheet({ kind: 'task', id: t.id }), []);
  const go = (t: Tab) => {
    haptic.select();
    setTab(t);
  };

  const tabs: Array<[Tab, string, JSX.Element]> = [
    ['today', 'Сегодня', <IconSun key="i" />],
    ['tasks', 'Задачи', <IconTasks key="i" />],
    ['finance', 'Финансы', <IconWallet key="i" />],
    ['planner', 'Ежедневник', <IconCalendar key="i" />],
  ];

  return (
    <ToastProvider>
      <div className="app">
        <main className="main">
          {tab === 'today' && (
            <TodayScreen
              name={name}
              onOpenTask={openTask}
              onPlan={(plan) => setSheet({ kind: 'plan', plan })}
              onAllTasks={() => go('tasks')}
            />
          )}
          {tab === 'tasks' && <TasksScreen onOpenTask={openTask} />}
          {tab === 'finance' && <FinanceScreen onQuickAdd={(prefill) => setSheet({ kind: 'add', prefill })} />}
          {tab === 'planner' && <PlannerScreen />}
        </main>

        <button type="button" className="fab" aria-label="Быстрое добавление" onClick={() => { haptic.tap(); setSheet({ kind: 'add', prefill: '' }); }}>
          <IconPlus size={26} stroke={2.5} />
        </button>

        <nav className="tabbar" aria-label="Разделы">
          {tabs.map(([id, label, icon]) => (
            <button key={id} type="button" aria-current={tab === id ? 'page' : undefined} onClick={() => go(id)}>
              {icon}
              {label}
            </button>
          ))}
        </nav>

        {sheet.kind === 'add' && <QuickAddSheet prefill={sheet.prefill} onClose={close} />}
        {sheet.kind === 'task' && <TaskDetailSheet taskId={sheet.id} onClose={close} />}
        {sheet.kind === 'plan' && <PlanPreviewSheet plan={sheet.plan} onClose={close} />}
      </div>
    </ToastProvider>
  );
}
