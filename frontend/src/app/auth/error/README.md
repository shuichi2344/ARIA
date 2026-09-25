# Authentication Error Page

This page handles authentication errors from Supabase, particularly expired invitation links.

## URL Parameters

The error page accepts the following query parameters:

- `error` - The error type (e.g., "access_denied")
- `error_code` - Specific error code (e.g., "otp_expired")
- `error_description` - Human-readable error description

## Expired Invitation Handling

When a user clicks an expired invitation link, they will be redirected to this page with:

```
/auth/error?error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired
```

The page will:
1. Display a clear error message indicating the invitation link has expired
2. Provide a direct email link to `aria.fypsupport@gmail.com` to request a new invitation
3. Show a "Request New Invitation" button that opens a pre-filled email
4. Provide a "Back to Home" button to return to the landing page

## Error Detection

The page automatically detects expired invitations by checking if:
- `error_code === 'otp_expired'`
- `error === 'access_denied'`
- `error_description` contains "expired" or "invalid"

## Flow Diagram

```
User clicks expired link
  ↓
Supabase auth callback (/auth/callback/route.ts)
  ↓
Detects OTP expired error
  ↓
Redirects to /auth/error with error params
  ↓
Error page displays message
  ↓
User clicks "Request New Invitation"
  ↓
Opens email to aria.fypsupport@gmail.com
```

## Related Files

- `/auth/callback/route.ts` - Handles Supabase auth callbacks and redirects to error page
- `/app/page.tsx` - Main landing page that also checks for hash-based auth errors
- `/components/auth/AuthModal.tsx` - Authentication modal component
