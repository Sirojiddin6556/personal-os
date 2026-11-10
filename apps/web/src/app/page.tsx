'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Client-side redirect: works both with the Node server and with the static
// GitHub Pages export (router.replace applies basePath).
export default function RootPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/today');
  }, [router]);
  return null;
}
