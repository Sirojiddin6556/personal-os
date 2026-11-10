'use client';

import { useEffect, useRef, useState } from 'react';

/** Public OAuth client id (Google Cloud Console → Credentials → Web client). */
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdApi {
  initialize(cfg: {
    client_id: string;
    callback: (r: GoogleCredentialResponse) => void;
    ux_mode?: 'popup' | 'redirect';
    auto_select?: boolean;
  }): void;
  renderButton(el: HTMLElement, opts: Record<string, unknown>): void;
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleIdApi } };
  }
}

const GIS_SRC = 'https://accounts.google.com/gsi/client';

function loadGis(): Promise<GoogleIdApi> {
  return new Promise((resolve, reject) => {
    const ready = () => (window.google?.accounts?.id ? resolve(window.google.accounts.id) : reject(new Error('GIS not available')));
    if (window.google?.accounts?.id) return ready();
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (!script) {
      script = document.createElement('script');
      script.src = GIS_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    script.addEventListener('load', ready, { once: true });
    script.addEventListener('error', () => reject(new Error('Не удалось загрузить Google Sign-In')), { once: true });
  });
}

/**
 * Official "Sign in with Google" button (Google Identity Services).
 * Calls onCredential with the signed ID token; the API verifies it at POST /auth/google.
 */
export function GoogleSignInButton({
  onCredential,
  onError,
}: {
  onCredential: (credential: string) => void;
  onError: (message: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cb = useRef(onCredential);
  cb.current = onCredential;
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGis()
      .then((gis) => {
        if (cancelled || !ref.current) return;
        gis.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (r) => cb.current(r.credential),
          ux_mode: 'popup',
        });
        gis.renderButton(ref.current, {
          type: 'standard',
          theme: document.documentElement.classList.contains('dark') ? 'filled_black' : 'outline',
          size: 'large',
          shape: 'pill',
          text: 'signin_with',
          locale: 'ru',
          width: Math.min(ref.current.offsetWidth || 360, 400),
        });
      })
      .catch((e: Error) => {
        setFailed(true);
        onError(e.message);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!GOOGLE_CLIENT_ID || failed) return null;
  return <div ref={ref} className="w-full flex justify-center min-h-[44px]" />;
}
