'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiRequest, ApiError, ValidationError } from '@/lib/api-client';
import { GoogleSignInButton, GOOGLE_CLIENT_ID } from '@/components/auth/GoogleSignInButton';

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOAuthLoading, setIsOAuthLoading] = useState(false);
  // Server may close sign-up (single-user self-hosting); hide the toggle then.
  const [registrationEnabled, setRegistrationEnabled] = useState(false);

  useEffect(() => {
    apiRequest<{ registration_enabled: boolean }>('GET', '/auth/config')
      .then((cfg) => setRegistrationEnabled(Boolean(cfg?.registration_enabled)))
      .catch(() => setRegistrationEnabled(false));
  }, []);

  const handleLoginSuccess = (token: string) => {
    // 1. Store in localStorage
    localStorage.setItem('personal_os_access_token', token);

    // 2. Store in cookie for SSR and middleware compatibility
    const isSecure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `personal_os_access_token=${encodeURIComponent(token)}; path=/; max-age=604800; SameSite=Lax${isSecure}`;

    // 3. Notify real-time WebSocket client
    window.dispatchEvent(new CustomEvent('auth:login', { detail: { token } }));

    // 4. Redirect to /today dashboard
    router.push('/today');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneralError(null);
    setFieldErrors({});
    setIsLoading(true);

    try {
      if (mode === 'register') {
        // Create the account (and its personal workspace), then log in below.
        await apiRequest<unknown, { email: string; password: string; full_name: string; timezone: string }>(
          'POST',
          '/auth/register',
          {
            body: {
              email: email.trim(),
              password,
              full_name: fullName.trim() || email.split('@')[0],
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
            },
          }
        );
      }
      const data = await apiRequest<LoginResponse, { email: string; password: string }>(
        'POST',
        '/auth/login',
        {
          body: { email, password },
        }
      );

      if (data?.access_token) {
        handleLoginSuccess(data.access_token);
      } else {
        throw new Error('Ответ сервера не содержит токен авторизации.');
      }
    } catch (err: unknown) {
      if (err instanceof ValidationError) {
        // RFC 9457 field-level errors
        setFieldErrors(err.fieldMap);
        setGeneralError(err.problem.detail || 'Пожалуйста, исправьте ошибки в форме.');
      } else if (err instanceof ApiError) {
        // RFC 9457 general problem details
        if (err.status === 401) {
          setGeneralError('Неверный email или пароль. Попробуйте еще раз.');
        } else if (err.status === 409) {
          setGeneralError('Аккаунт с таким email уже есть. Войдите в него.');
        } else if (err.status === 429) {
          setGeneralError('Слишком много попыток входа. Подождите минуту и попробуйте снова.');
        } else {
          setGeneralError(err.problem.detail || err.problem.title || `Ошибка входа (${err.status})`);
        }
      } else if (err instanceof Error) {
        setGeneralError(
          err.message === 'Failed to fetch'
            ? 'Сервер API недоступен. Если он на бесплатном Render, подождите минуту, пока он проснётся, и попробуйте снова.'
            : err.message
        );
      } else {
        setGeneralError('Произошла непредвиденная ошибка при входе.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleCredential = async (credential: string) => {
    setIsOAuthLoading(true);
    setGeneralError(null);
    try {
      const data = await apiRequest<LoginResponse, { credential: string }>('POST', '/auth/google', {
        body: { credential },
      });
      if (!data?.access_token) throw new Error('Ответ сервера не содержит токен авторизации.');
      handleLoginSuccess(data.access_token);
    } catch (err) {
      if (err instanceof ApiError) {
        setGeneralError(err.problem.detail || err.problem.title || `Ошибка входа через Google (${err.status})`);
      } else if (err instanceof Error) {
        setGeneralError(
          err.message === 'Failed to fetch'
            ? 'Сервер API недоступен. Если он на бесплатном Render, подождите минуту, пока он проснётся, и попробуйте снова.'
            : err.message
        );
      } else {
        setGeneralError('Не удалось войти через Google.');
      }
    } finally {
      setIsOAuthLoading(false);
    }
  };

  const isDevBuild = process.env.NODE_ENV !== 'production';

  const handleDemoLogin = () => {
    // Development only: lets the UI open without an API (see (app)/layout bypass).
    const demoToken = 'demo-jwt-token-' + Date.now();
    localStorage.setItem('personal_os_bypass_auth', 'true');
    handleLoginSuccess(demoToken);
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-md bg-surface border border-border rounded-2xl shadow-xl p-6 sm:p-8 space-y-6 animate-fade-in">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-12 h-12 rounded-xl bg-primary text-white items-center justify-center font-bold text-2xl shadow-md">
            P
          </div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            Personal OS
          </h1>
          <p className="text-sm text-text-muted">
            Персональная операционная система
          </p>
        </div>

        {/* General Error Alert (RFC 9457) */}
        {generalError && (
          <div
            role="alert"
            className="p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-xs flex items-start gap-2.5 animate-slide-in"
          >
            <svg className="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="leading-relaxed flex-1">{generalError}</span>
          </div>
        )}

        {/* Sign in with Google (shown only when NEXT_PUBLIC_GOOGLE_CLIENT_ID is set) */}
        {GOOGLE_CLIENT_ID && (
          <div className="space-y-3">
            <div aria-busy={isOAuthLoading} className={isOAuthLoading ? 'opacity-60 pointer-events-none' : undefined}>
              <GoogleSignInButton onCredential={handleGoogleCredential} onError={setGeneralError} />
            </div>
            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-border"></div>
              <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-text-muted">
                или по email
              </span>
              <div className="flex-grow border-t border-border"></div>
            </div>
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div className="space-y-1.5">
              <label htmlFor="full_name" className="block text-xs font-semibold text-text-secondary">
                Имя
              </label>
              <input
                id="full_name"
                type="text"
                required
                autoComplete="name"
                maxLength={100}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Как к вам обращаться"
                className="w-full px-3.5 py-2.5 rounded-xl bg-surface-muted border border-border text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              />
            </div>
          )}

          {/* Email Field */}
          <div className="space-y-1.5">
            <label
              htmlFor="email"
              className="block text-xs font-semibold text-text-secondary"
            >
              Электронная почта
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) {
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.email;
                    return next;
                  });
                }
              }}
              placeholder="user@example.com"
              className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-muted border text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all ${
                fieldErrors.email ? 'border-status-error ring-1 ring-status-error' : 'border-border'
              }`}
            />
            {fieldErrors.email && (
              <p className="text-[11px] text-status-error font-medium">
                {fieldErrors.email}
              </p>
            )}
          </div>

          {/* Password Field */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-text-secondary"
              >
                Пароль
              </label>
            </div>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) {
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.password;
                    return next;
                  });
                }
              }}
              placeholder="••••••••"
              className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-muted border text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all ${
                fieldErrors.password ? 'border-status-error ring-1 ring-status-error' : 'border-border'
              }`}
            />
            {fieldErrors.password && (
              <p className="text-[11px] text-status-error font-medium">
                {fieldErrors.password}
              </p>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary hover:bg-primary-600 active:scale-[0.98] text-white font-semibold text-sm transition-all shadow-md hover:shadow-lg disabled:opacity-60 cursor-pointer"
          >
            {isLoading ? (
              <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
            ) : null}
            <span>
              {isLoading
                ? mode === 'register' ? 'Создаём аккаунт...' : 'Вход...'
                : mode === 'register' ? 'Создать аккаунт' : 'Войти в систему'}
            </span>
          </button>
          {mode === 'register' && (
            <p className="text-[11px] text-text-muted text-center">Пароль — не короче 8 символов.</p>
          )}
        </form>

        {(registrationEnabled || mode === 'register') && (
        <div className="text-center text-xs text-text-muted">
          {mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setGeneralError(null);
              setFieldErrors({});
            }}
            className="text-primary hover:underline font-semibold"
          >
            {mode === 'login' ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </div>
        )}

        {/* Development / Demo Quick Access (never in production builds) */}
        {isDevBuild && (
        <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-text-muted">
          <span>Режим разработки?</span>
          <button
            type="button"
            onClick={handleDemoLogin}
            className="text-primary hover:underline font-medium cursor-pointer"
          >
            Быстрый демо-вход →
          </button>
        </div>
        )}
      </div>
    </div>
  );
}
