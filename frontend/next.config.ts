import type { NextConfig } from "next";

const appOrigin = "https://aria-fyp.vercel.app";
const apiOrigin = process.env.NEXT_PUBLIC_API_URL
  ? new URL(process.env.NEXT_PUBLIC_API_URL).origin
  : "http://localhost:8000";
const supabaseOrigin = process.env.NEXT_PUBLIC_SUPABASE_URL
  ? new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).origin
  : "https://*.supabase.co";

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${supabaseOrigin}`,
  `font-src 'self' data: ${supabaseOrigin}`,
  `connect-src 'self' ${apiOrigin} ${supabaseOrigin} ${supabaseOrigin.replace(/^https:/, "wss:")}`,
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    const securityHeaders = [
      { key: "Content-Security-Policy", value: contentSecurityPolicy },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Access-Control-Allow-Origin", value: appOrigin },
      { key: "Cache-Control", value: "private, no-store, max-age=0, must-revalidate" },
    ];

    return [
      { source: "/:path*", headers: securityHeaders },
      {
        source: "/_next/static/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
