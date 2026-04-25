---
name: vitest-rtl-playwright
description: Use when writing or fixing tests. Three layers — pure unit (Vitest), component (RTL), e2e (Playwright). MSW mocks REST.
---

# Test layers

## Choose the layer
- Pure functions, Zod schemas, query-key factories, store slices, derivations → **Vitest only**, no DOM
- Components, hooks → **Vitest + RTL**, mock the network with MSW, never mock TanStack Query
- Auth flows, multi-page journeys, anything crossing route boundaries → **Playwright**

If a component test needs to mock a route or Clerk session deeply, escalate to Playwright instead.

## RTL queries (use in this priority order)
1. `getByRole(name: ...)` — accessible name
2. `getByLabelText` — form fields
3. `getByText` — non-interactive content
4. `getByTestId` — last resort, only when no semantic role exists

Never use `getByClassName`, `container.querySelector`, or DOM traversal.

## Async
- `await screen.findBy*` for elements that appear after async work
- `await waitFor` only for non-DOM assertions
- Never `await new Promise(setTimeout)` or `page.waitForTimeout` — guaranteed flake

## MSW
One handler set in `src/test/handlers.ts`, started in `src/test/setup.ts` via `setupServer`. Override per-test with `server.use(...)`. Never mock `fetch` globally.

## TanStack Query in tests
Wrap with a fresh `QueryClient` per test (retries off, gc time 0):
```ts
const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
```

## Clerk in tests
- RTL: mock `@clerk/clerk-react` (or `@clerk/react`) with `vi.mock` — return stub `useAuth`/`useUser` matching the test's signed-in state
- Playwright: use Clerk's testing tokens (`@clerk/testing/playwright`); never type credentials into the UI

## Playwright
- One `test.describe` per user journey
- Use `page.getByRole` matching RTL conventions
- Tests run against `pnpm dev` — `webServer` config in `playwright.config.ts` handles startup
- Coverage target: happy path + each error/empty state + one regression case for non-trivial branches; don't pad with redundant assertions
