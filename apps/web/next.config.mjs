/** @type {import('next').NextConfig} */

// STATIC_EXPORT=1 builds plain HTML/JS for GitHub Pages (no Node server):
// `out/` is served from NEXT_PUBLIC_BASE_PATH (e.g. /personal-os).
const staticExport = process.env.STATIC_EXPORT === '1';
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const securityHeaders = [
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
];

const nextConfig = staticExport
  ? {
      output: 'export',
      basePath,
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : {
      output: 'standalone',
      experimental: {
        instrumentationHook: true,
      },
      headers: async () => [{ source: '/(.*)', headers: securityHeaders }],
    };

export default nextConfig;
