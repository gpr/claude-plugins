---
name: rails-test-impact
description: Picks the minimum RSpec set that covers a code change when the user edits a controller, model, service, or concern, including request, integration, and feature specs that reference the changed constant.
---

## When to run

Before answering "which specs should I run?" or committing a Rails change. The PostToolUse hook runs one spec per edited file; this skill expands the impact set to cover indirect coverage.

## Method

1. **Resolve the changed file to its constant.** `app/models/order.rb` → `Order`. `app/controllers/api/v1/orders_controller.rb` → `Api::V1::OrdersController`. Use the helper below — it understands `app/`, `lib/`, and nested namespaces.

2. **Find the direct spec.** `spec/<same path>_spec.rb` if it exists.

3. **Find referring specs.** Any spec file that names the constant (`describe Order`, `let(:order) { Order.create }`, `Order.find(...)`). Include request specs, integration specs, and feature specs — they don't live next to the production file.

4. **Report the set and the reason.** Output the spec paths, one per line, followed by a short "why each" line.

## Helper

Run `scripts/impacted-specs.rb <changed-file>` to list the impacted specs:

```bash
ruby ${CLAUDE_PLUGIN_ROOT}/scripts/impacted-specs.rb app/models/order.rb
```

It prints spec paths on stdout, one per line.

## Invocation

Feed the list into RSpec:

```bash
bundle exec rspec $(ruby ${CLAUDE_PLUGIN_ROOT}/scripts/impacted-specs.rb <changed-file>)
```

## Edge cases

- **Concerns.** `app/models/concerns/foo.rb` defines `Foo`; any model that `include Foo` is affected. The helper expands this via `rg 'include Foo\b' app/models`.
- **Service objects without a constant.** Fall back to path-based spec lookup only.
- **No direct spec.** Report the miss; don't silently skip.
- **Feature specs in `spec/system/`.** Included when they reference the constant.
