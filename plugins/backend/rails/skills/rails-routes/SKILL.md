---
name: rails-routes
description: Inspects Rails routes, finds which controller action handles a URL, and scaffolds new API routes when the user asks about routing, encounters 404s with no matching route, or wants to add or modify routes.rb.
---

## Inspecting existing routes

Run `bin/rails routes` for the full table. For a focused search:

- By controller: `bin/rails routes -c users` (shows all UsersController routes)
- By path fragment: `bin/rails routes -g /api/v1`
- Expanded, human-readable: `bin/rails routes --expanded`

In a JSON API app the table can still be large. Prefer `-c` or `-g` over the full dump.

## Adding routes (API conventions)

Namespace versioned APIs and use `only:` to avoid exposing unused actions:

```ruby
# config/routes.rb
Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      resources :posts, only: [:index, :show, :create, :update, :destroy] do
        resources :comments, only: [:index, :create]
      end
    end
  end
end
```

## Debugging a 404

1. Check HTTP method — GET vs POST mismatch is the most common cause.
2. Confirm the route exists: `bin/rails routes -g <path>`.

Less common:

3. `constraints:` on format/params may cause the route to exist but not match.
4. Controller file missing at the namespaced path Rails expects (e.g. `app/controllers/api/v1/posts_controller.rb` for `Api::V1::PostsController`).

## Route helpers

After adding a route, the helper name is visible in `bin/rails routes`. For the example above: `api_v1_posts_path`, `api_v1_post_path(id)`, `api_v1_post_comments_path(post_id)`.
