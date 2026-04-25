---
name: error-and-loading
description: Use when adding routes or components that fetch data. Loading and error states are required, not optional. Covers Suspense, ErrorBoundary, route-level pendingComponent/errorComponent.
---

# Error and loading states

Every data-driven route or component has three branches: loading, error, success. Skipping any of them ships a bug.

## Layer the boundaries

Three layers, outermost to innermost:

1. **App-level ErrorBoundary** (in `__root.tsx`) — catches anything route-level didn't. Logs to Sentry/console; renders a generic "something went wrong" with a refresh action
2. **Route-level** — `errorComponent` and `pendingComponent` in the route definition
3. **Component-level** — only when a sub-region of the page fetches independently and you want it to load/error without taking down the whole route

Don't add inner boundaries unless they actually help the user — every boundary is a place where errors stop bubbling.

## Route pattern (TanStack Router + Suspense Query)

```tsx
export const Route = createFileRoute('/users/$userId')({
  loader: ({ params, context }) =>
    context.queryClient.ensureQueryData(userQueryOptions(params.userId)),
  pendingComponent: UserSkeleton,
  errorComponent: UserError,
  component: UserPage,
})

function UserPage() {
  const { userId } = Route.useParams()
  const { data } = useSuspenseQuery(userQueryOptions(userId)) // never undefined
  return <UserCard user={data} />
}
```

Key invariant: when you use `useSuspenseQuery`, `data` is typed as non-nullable. Don't write `data?.name` — that's a tell that someone mixed `useQuery` and `useSuspenseQuery`.

## pendingComponent vs Suspense fallback
- `pendingComponent` runs while the loader is fetching, **before** the component mounts
- `<Suspense fallback>` inside the component runs when a child triggers Suspense
- Use `pendingComponent` for the route's primary data; reserve `<Suspense>` for sub-regions with independent fetches

## errorComponent contract

```tsx
function UserError({ error, reset }: ErrorComponentProps) {
  if (error instanceof HTTPError && error.status === 404) return <NotFound />
  if (error instanceof HTTPError && error.status === 403) return <Forbidden />
  return <GenericError error={error} retry={reset} />
}
```

- `reset` re-runs the loader. Wire it to a "Retry" button
- Branch on error shape (HTTP status, Zod parse error) for distinct UX
- Don't swallow the error silently — if the user can't act on it, log it

## Loading skeletons
- Skeletons mirror the final layout, not generic spinners. A spinner where a card will appear causes layout shift
- Build skeletons from shadcn `<Skeleton>` primitives, not custom CSS animations
- TanStack Router defaults: `pendingMs: 1000` (don't show pending until loader takes 1s+), `pendingMinMs: 500` (once shown, keep it visible 500ms+ to avoid flash). Tune per route — e.g. lower `pendingMs` on routes you know are slow

## Mutation states
Mutations have their own `isPending` / `isError`. Wire button states to `mutation.isPending` for `disabled` and a spinner; surface `mutation.error` near the form (toast or inline). Don't hide errors in console.

## Don'ts
- Don't write `if (isLoading) return <Spinner />; if (error) return <Err />;` chains in components — that's what `pendingComponent` and `errorComponent` are for
- Don't catch errors in `queryFn` and return a fallback shape — let them throw so Query routes them to the boundary
- Don't render the route component conditionally on `data` truthiness when using Suspense Query — `data` is guaranteed
- Don't use `<ErrorBoundary>` from `react-error-boundary` directly inside a route that already has `errorComponent` — they fight
