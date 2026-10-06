---
name: rails-render-deploy
description: Bridges Rails config to a Render Blueprint when deploying a Rails API, auditing render.yaml against Rails env expectations, or debugging a failed release phase on Render.
---

## When to run

- Authoring or editing a `render.yaml` for a Rails API app.
- Auditing an existing `render.yaml` against what a Rails app actually needs.
- Debugging a Render release-phase failure (migrations, seeds, asset precompile).

Pairs with the `render-blueprint` skill from the `render` plugin — that skill owns Blueprint syntax and Render-side concerns; this one owns the Rails-side contract.

## The Rails → Render contract

A Rails API service on Render needs:

| Requirement                 | Render field                          | Notes                                                                    |
| :-------------------------- | :------------------------------------ | :----------------------------------------------------------------------- |
| `DATABASE_URL`              | `envVars` from `fromDatabase`         | Set by Render when a `databases:` entry is present — do not hardcode.    |
| `SECRET_KEY_BASE`           | `envVars` with `generateValue: true`  | Required in production. Never commit.                                    |
| `RAILS_MASTER_KEY`          | `envVars` synced from project secrets | If using encrypted credentials.                                          |
| `RAILS_ENV=production`      | `envVars`                             | Explicit; don't rely on defaults.                                        |
| `RAILS_LOG_TO_STDOUT=true`  | `envVars`                             | Render captures stdout — Rails otherwise writes to `log/production.log`. |
| `RAILS_SERVE_STATIC_FILES`  | `envVars`                             | `"true"` for API-only apps without a CDN in front.                       |
| Release phase migrations    | `preDeployCommand`                    | `./bin/rails db:migrate` — blocks deploy on migration failure.           |
| Health check                | `healthCheckPath`                     | Rails needs a route returning 200 (e.g. `/up` exists in Rails 7.1+).     |
| Ruby version                | `runtime: ruby` + `.ruby-version`     | Render reads `.ruby-version`; keep it in sync with `Gemfile`.            |

## Audit checklist

Given a `render.yaml` + Rails app, verify:

1. **`DATABASE_URL` is wired from a `databases:` entry, not hardcoded.**
2. **`SECRET_KEY_BASE` is present** as `generateValue: true` or a sync'd secret. An absent key boots the app but 500s on any session/cookie.
3. **`preDeployCommand` runs migrations** — otherwise schema drift breaks the first request after deploy.
4. **`healthCheckPath` hits a route that exists.** Confirm with `bin/rails routes -g <path>`. Rails 7.1+ ships `/up`; older apps need a custom endpoint.
5. **`buildCommand` covers asset precompile only if assets exist.** An API-only app with no `app/assets/` should skip `assets:precompile` to save build time.
6. **`plan` and region match.** Starter plans sleep; stateful jobs need `standard` or higher.

## Release phase gotchas

- **Migration timeouts.** Long migrations exceed Render's release timeout. Use `algorithm: :concurrently` or split into pre- and post-deploy steps.
- **Seed data in release.** Never run `db:seed` in `preDeployCommand` — it reruns on every deploy. Gate it, or move it to a one-off job.
- **Asset precompile in release, not build.** If `buildCommand` runs `assets:precompile`, a missing `DATABASE_URL` during build can crash initializers that eager-load. Add `SECRET_KEY_BASE=x DATABASE_URL=x` placeholders for build, or defer compile to release.

## Cross-references

- For Blueprint syntax, service types, and Render-specific features: invoke `render-blueprint` (from the `render` plugin).
- For migration safety during release phase: invoke `rails-migrations`.
- For auditing routes referenced by `healthCheckPath`: invoke `rails-routes`.
