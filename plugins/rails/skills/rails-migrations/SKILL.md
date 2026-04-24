---
name: rails-migrations
description: Generate, inspect, and safely manage Rails migrations. Use when the user wants to add/change/drop columns, indexes, or tables, or when they're resolving a migration conflict or failed migration.
---

# Rails Migrations

## Generating migrations

Prefer generators — they produce the right file name and timestamp:

```bash
bin/rails g migration AddStatusToPosts status:string
bin/rails g migration AddIndexToPostsStatus
bin/rails g migration CreateAuthTokens user:references token:string:uniq expires_at:datetime
```

For a new model with a backing table:

```bash
bin/rails g model Post title:string body:text published:boolean
```

## Running and rolling back

```bash
bin/rails db:migrate                # run pending
bin/rails db:migrate:status         # list what's up/down
bin/rails db:rollback               # roll back the last migration
bin/rails db:rollback STEP=3        # roll back 3
bin/rails db:migrate:redo           # rollback + migrate (for iterating)
```

In a multi-env API app, remember to run against the test DB too before writing specs:

```bash
bin/rails db:migrate RAILS_ENV=test
```

## Production safety

Migrations on large production tables require two-step patterns (add nullable → backfill → enforce; concurrent indexes; `ignored_columns` before drop). See [references/production-safety.md](references/production-safety.md) before editing schemas that touch high-row-count tables.

## Resolving conflicts

1. Rebase.
2. Renumber the timestamp past main's.
3. `bin/rails db:rollback`, then `bin/rails db:migrate` in the new order.
4. Regenerate `db/schema.rb` cleanly — don't hand-edit it.
