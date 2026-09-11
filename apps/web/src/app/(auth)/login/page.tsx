'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiRequest, ApiError, ValidationError } from '@/lib/api-client';

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOAuthLoading, setIsOAuthLoading] = useState(false);

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
        } else {
          setGeneralError(err.problem.detail || err.problem.title || `Ошибка входа (${err.status})`);
        }
      } else if (err instanceof Error) {
        setGeneralError(err.message);
      } else {
        setGeneralError('Произошла непредвиденная ошибка при входе.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleOAuth = async () => {
    setIsOAuthLoading(true);
    setGeneralError(null);
    try {
      // Retrieve Google OAuth authorization URL from API or fallback
      const data = await apiRequest<{ auth_url: string }>('GET', '/integrations/google/auth-url');
      if (data?.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error('Не удалось получить ссылку для входа через Google.');
      }
    } catch (err) {
      // Fallback for local development or direct OAuth redirect
      window.location.href = '/v1/integrations/google/authorize';
    } finally {
      setIsOAuthLoading(false);
    }
  };

  const handleDemoLogin = () => {
    // Fast mock login token for local development / testing
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

        {/* OAuth Buttons */}
        <div className="space-y-3">
          <button
            type="button"
            onClick={handleGoogleOAuth}
            disabled={isOAuthLoading}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-xl border border-border bg-surface-elevated hover:bg-surface-muted text-sm font-medium text-text-primary transition-colors disabled:opacity-60"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.64v3.03h3.88c2.27-2.09 3.66-5.17 3.66-9.11z"
              />
              <path
                fill="#34A853"
                d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.03c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.24v3.13C3.26 21.36 7.33 24 12 24z"
              />
              <path
                fill="#FBBC05"
                d="M5.28 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.58H1.24C.45 8.14 0 9.97 0 12s.45 3.86 1.24 5.42l4.04-3.13z"
              />
              <path
                fill="#EA4335"
                d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.24 6.58l4.04 3.13c.95-2.83 3.6-4.96 6.72-4.96z"
              />
            </svg>
            <span>{isOAuthLoading ? 'Подключение...' : 'Войти через Google'}</span>
          </button>

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-border"></div>
            <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-text-muted">
              или по email
            </span>
            <div className="flex-grow border-t border-border"></div>
          </div>
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
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
            <span>{isLoading ? 'Вход...' : 'Войти в систему'}</span>
          </button>
        </form>

        {/* Development / Demo Quick Access */}
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
      </div>
    </div>
  );
}
