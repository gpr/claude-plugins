---
name: env-vars
description: Use when adding configuration values, API URLs, feature flags, or anything environment-dependent. Vite + TS conventions; fail-fast on missing values.
---

# Environment variables

## Rules

- All client-exposed vars **must** be prefixed `VITE_` — anything else is invisible to the browser
- Anything in a `VITE_` var is **public**: it ships in the JS bundle. Never put secrets there. No API keys for paid services, no database URLs, no JWT signing keys
- Server secrets stay on the server. If you need a value on the client, proxy through your API
- Don't read `process.env` — it doesn't exist in Vite browser builds. Use `import.meta.env`

## Single source of truth

One module, `src/env.ts`, that parses and exports validated config. Every other file imports from there.

```ts
// src/env.ts
import { z } from 'zod'

const schema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_CLERK_PUBLISHABLE_KEY: z.string().startsWith('pk_'),
  VITE_SENTRY_DSN: z.string().url().optional(),
  MODE: z.enum(['development', 'production', 'test']), // built-in, no VITE_ prefix
})

const parsed = schema.safeParse(import.meta.env)
if (!parsed.success) {
  console.error('Invalid env:', parsed.error.flatten().fieldErrors)
  throw new Error('Missing or invalid environment variables')
}

export const env = parsed.data
```

This throws at module load — failure is loud and immediate, not a runtime null deref three pages deep.

## Typing

```ts
// src/vite-env.d.ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_CLERK_PUBLISHABLE_KEY: string
  readonly VITE_SENTRY_DSN?: string
}
interface ImportMeta { readonly env: ImportMetaEnv }
```

Keep this in sync with the Zod schema. The Zod schema is runtime truth; the TS types are editor convenience.

## File layout

- `.env` — committed defaults safe for everyone
- `.env.local` — gitignored, developer-specific overrides
- `.env.development` / `.env.production` — mode-specific, committed if values aren't sensitive
- `.env.test` — test-mode values, committed

Never commit a file containing real secrets. If a secret leaks into git, rotate it — don't just remove the file.

## Build-time vs runtime

Vite **inlines** `import.meta.env.VITE_*` values at build time. That means:
- Changing a var requires a rebuild — no runtime config swap
- The same build cannot serve dev and prod with different API URLs

If you need runtime config (e.g. one container image deployed to staging and prod), serve `/config.json` from your backend and fetch it at app start. Don't try to make Vite do this.

## Test environment
- Vitest reads `.env.test` automatically when `MODE=test`
- For per-test overrides, use `vi.stubEnv('VITE_API_BASE_URL', '...')` in `beforeEach` and `vi.unstubAllEnvs()` in `afterEach`

## Don'ts

- Don't access `import.meta.env.VITE_FOO` directly in feature code — import from `src/env.ts` so the validation runs first
- Don't fall back to a default URL with `||`: `import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'` masks misconfiguration
- Don't read env vars inside React render — read them once at module scope; they don't change between renders
- Don't put a feature flag system in env vars beyond a handful of toggles. For real flag management, use a flags service
