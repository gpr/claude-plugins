---
name: tanstack-router
description: "Encodes file-based TanStack Router conventions with type-safe params and Zod-validated search params. Invoke when adding routes, writing route loaders, defining search param schemas, or navigating programmatically."
---

# TanStack Router

## Layout
File-based routes in `src/routes/`. Generate `routeTree.gen.ts` via the Vite plugin — never hand-edit it.

- `__root.tsx` — root layout, providers (QueryClient, Clerk), `<Outlet />`
- `_authenticated.tsx` — pathless layout that wraps protected routes; gate with Clerk `<SignedIn>` / redirect from `beforeLoad`
- `users/$userId.tsx` — dynamic segment; access via `Route.useParams()`

## Search params (Zod)
Validate every search param schema. Type comes free.

```ts
const searchSchema = z.object({ page: z.number().int().min(1).default(1), q: z.string().optional() })
export const Route = createFileRoute('/users/')({
  validateSearch: searchSchema,
  loaderDeps: ({ search: { page, q } }) => ({ page, q }),
  loader: ({ deps, context }) => context.queryClient.ensureQueryData(usersListOptions(deps)),
  component: UsersList,
})
```

## Loaders + TanStack Query
- Inject `queryClient` into router context at root
- Loaders call `ensureQueryData(queryOptions)` — same `queryOptions` reused in `useSuspenseQuery` inside the component
- Co-locate the `queryOptions` factory with its endpoint module

## Navigation
- `<Link to="/users/$userId" params={{ userId: id }} search={{ tab: 'profile' }} />` — params and search are typed against the target route
- Programmatic: `useNavigate()` returns a typed `navigate` function
- Never build URLs as strings

## Auth gating
`beforeLoad` in `_authenticated.tsx`:
```ts
beforeLoad: ({ context, location }) => {
  if (!context.auth.isSignedIn) throw redirect({ to: '/sign-in', search: { redirect: location.href } })
}
```
Clerk's `useAuth()` is read once at root and passed via `context`.
