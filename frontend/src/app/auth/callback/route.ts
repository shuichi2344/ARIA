/**
 * Forward Supabase email confirmation and invitation tokens to a browser route.
 * Supabase sessions must be established in the browser so they persist for ARIA.
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const error = requestUrl.searchParams.get('error');
  const errorDescription = requestUrl.searchParams.get('error_description');
  const errorCode = requestUrl.searchParams.get('error_code');

  if (error) {
    const isExpired = errorCode === 'otp_expired'
      || error === 'access_denied'
      || errorDescription?.toLowerCase().includes('expired')
      || errorDescription?.toLowerCase().includes('invalid');

    if (isExpired) {
      const params = new URLSearchParams({
        error,
        error_code: errorCode || '',
        error_description: errorDescription || error,
      });
      return NextResponse.redirect(`${requestUrl.origin}/auth/error?${params.toString()}`);
    }

    return NextResponse.redirect(
      `${requestUrl.origin}/?error=${encodeURIComponent(errorDescription || error)}`,
    );
  }

  const finishUrl = new URL('/auth/finish', requestUrl.origin);
  for (const key of ['code', 'token_hash', 'type']) {
    const value = requestUrl.searchParams.get(key);
    if (value) finishUrl.searchParams.set(key, value);
  }

  if (finishUrl.searchParams.has('code') || finishUrl.searchParams.has('token_hash')) {
    return NextResponse.redirect(finishUrl);
  }

  return NextResponse.redirect(requestUrl.origin);
}
