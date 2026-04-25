---
name: tanstack-query
description: Use when fetching, mutating, or caching server state. Project conventions for TanStack Query v5 + REST + Clerk auth.
---

# TanStack Query (REST + Clerk)

## Query keys
Hierarchical, factory-defined per resource. Never inline.

```ts
// src/api/keys.ts
export const keys = {
  users: {
    all: ['users'] as const,
    list: (filters: UserFilters) => [...keys.users.all, 'list', filters] as const,
    detail: (id: string) => [...keys.users.all, 'detail', id] as const,
  },
} as const
```

Invalidate by prefix: `qc.invalidateQueries({ queryKey: keys.users.all })`.

## Fetch client
One typed client in `src/api/client.ts`. Always:
- pulls token via `useAuth().getToken()` from Clerk inside a hook factory — never store tokens
- validates response with the Zod schema co-located with the endpoint
- throws `HTTPError` on `!res.ok` so Query routes it to the route's `errorComponent`

```ts
// src/api/http-error.ts
export class HTTPError extends Error {
  constructor(public status: number, public body?: unknown) {
    super(`HTTP ${status}`)
    this.name = 'HTTPError'
  }
}

// src/api/users.ts — endpoint module pattern
const UserSchema = z.object({ id: z.string(), email: z.string().email() })
export type User = z.infer<typeof UserSchema>

export const useUser = (id: string) => {
  const { getToken } = useAuth()
  return useQuery({
    queryKey: keys.users.detail(id),
    queryFn: async ({ signal }) => {
      const token = await getToken()
      const res = await fetch(`${env.VITE_API_BASE_URL}/users/${id}`, {
        signal,
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new HTTPError(res.status, await res.text().catch(() => undefined))
      return UserSchema.parse(await res.json())
    },
  })
}
```

## Mutations
- Always pair with `onSuccess` invalidation of the affected key prefix
- Use `onMutate` for optimistic updates only when UX demands it; always implement `onError` rollback
- Return `Promise<void>` from `onSuccess` if it awaits invalidation, so `isPending` covers refetch

## Suspense
Use `useSuspenseQuery` inside route loaders / Suspense boundaries. Never mix `useQuery` and `useSuspenseQuery` for the same key. See `error-and-loading` skill for the route-level `pendingComponent` / `errorComponent` pattern.

## Don'ts
- No `keepPreviousData` (removed in v5) — use `placeholderData: keepPreviousData` from the import
- No `onSuccess`/`onError` on `useQuery` (removed in v5) — handle in component or via `meta`
- No global `enabled: false` to gate auth — gate at route level via Clerk `<Protect>` instead
