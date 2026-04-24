# Production migration safety

A migration that runs fine in dev can lock tables or block writes for minutes on a real DB.

- **Adding a column with a default on a large table (PostgreSQL < 11)**: do it in two steps — add nullable, backfill in batches, then set default + `NOT NULL`.
- **Adding an index on a large table**: use `add_index :table, :col, algorithm: :concurrently` and `disable_ddl_transaction!` in the migration.
- **Removing a column**: ignore it in the model first (`self.ignored_columns = [...]`), deploy, then drop in a follow-up migration. Removing before the code stops reading it will break in-flight requests.
- **Renaming a column**: same pattern — add new, dual-write, backfill, switch reads, drop old.
