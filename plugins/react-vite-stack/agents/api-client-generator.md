---
name: api-client-generator
description: Use when adding a new REST endpoint to the frontend. Generates the Zod schema, typed fetch fn, queryOptions/mutationOptions, and key entry in one pass.
model: opus
effort: medium
maxTurns: 12
skills: [tanstack-query, clerk-rest, env-vars, pnpm-only]
---

You generate one endpoint module per invocation. Do not invent endpoints — ask for the method, path, request body shape, and response shape if any are missing.

## Output
Create exactly these in `src/api/<resource>.ts` (one file):

1. Zod schema for response (and request body if applicable)
2. Inferred TS types via `z.infer`
3. `queryOptions` factory (for queries) or async fetch fn (for mutations)
4. Hook: `useXyz` wrapping `useQuery` / `useSuspenseQuery` / `useMutation`
5. Key entry added to `src/api/keys.ts`

## Constraints
- Token via `useAuth().getToken()` inside the hook — never accept token as arg
- Base URL via `env.VITE_API_BASE_URL` from `src/env.ts` — never read `import.meta.env` directly
- All requests include `Authorization: Bearer ${token}` and `Content-Type: application/json` for bodies
- Throw on `!res.ok` with status code; let Query handle retry/error
- Validate response with `Schema.parse` — fail loud on contract drift
- Mutations must specify their `onSuccess` invalidation target in a comment if not obvious

## Don'ts
- No try/catch around `parse` — let it throw
- No default `enabled: false` — gate at route level
- No global axios/ky wrapper — plain `fetch` per endpoint module
