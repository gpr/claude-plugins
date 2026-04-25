---
name: clerk-rest
description: Use when adding auth, calling protected API endpoints, or gating routes/components. Clerk + REST conventions.
---

# Clerk + REST

## Package
- New projects: install `@clerk/react` (current package as of 2026)
- Existing projects on `@clerk/clerk-react`: keep using it; that package is in long deprecation but still functional. Don't mix imports from both
- Detect which is in use by reading `package.json` before importing; don't assume

## Setup
- `<ClerkProvider publishableKey={env.VITE_CLERK_PUBLISHABLE_KEY}>` wraps the app at the router root (import `env` from `src/env.ts`; see `env-vars` skill)
- Browser SDK only. Never import from `@clerk/nextjs`, `@clerk/clerk-js`, or `@clerk/backend` on the frontend

## Same-origin vs cross-origin
- **Same origin** (frontend and API on same domain): Clerk's session cookie is sent automatically. No `Authorization` header needed. Just call `fetch`
- **Cross-origin** (e.g. `app.example.com` calling `api.example.com`): use `getToken()` and set `Authorization: Bearer ${token}`

## Token retrieval (cross-origin)
Always through `useAuth().getToken()`. Never read tokens from `localStorage`, `document.cookie`, or `window.Clerk` — those are unstable internals.

```ts
const { getToken } = useAuth()
const token = await getToken() // returns string | null
// For a custom JWT template: getToken({ template: 'api' })
```

Token is short-lived (~60s); call `getToken()` per request, don't cache.

## Route guards
- Top-level: `_authenticated.tsx` layout with `beforeLoad` redirect (see tanstack-router skill)
- Inline: `<SignedIn>{children}</SignedIn>` / `<SignedOut><RedirectToSignIn /></SignedOut>`
- Role/permission: `<Protect role="admin" fallback={<Forbidden />}>`

## Component-level identity
- `useUser()` for the user object (display name, avatar, email)
- `useAuth()` for `isSignedIn`, `isLoaded`, `userId`, `getToken`, `signOut`
- Always check `isLoaded` before branching on `isSignedIn`. Branching too early flashes signed-out UI on every refresh

## Webhooks → backend
The frontend never receives webhook events. If asked to "sync user to backend on signup," that's a backend concern (Clerk webhook → your API). Do not implement it on the client.

## Don'ts
- Don't store the token in Zustand or React state — it goes stale
- Don't pass `getToken` through props — call `useAuth()` where needed
- Don't gate API calls with `enabled: !!token` in TanStack Query — gate the route via `<SignedIn>` so the query never runs unauthenticated
