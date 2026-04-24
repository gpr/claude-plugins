---
name: rails-api-conventions
description: Conventions for a Rails API-only backend. Use when scaffolding controllers, choosing status codes, shaping error envelopes, picking a serializer, adding pagination, versioning endpoints, or reviewing API PRs.
---

# Rails API Conventions

## Controller shape

Inherit from `ActionController::API` (not `::Base`) in an API-only app. Keep actions thin — move logic to models, services, or query objects.

```ruby
module Api
  module V1
    class PostsController < ApplicationController
      before_action :set_post, only: [:show, :update, :destroy]

      def index
        posts = Post.page(params[:page]).per(params[:per_page] || 25)
        render json: PostSerializer.new(posts, meta: pagination_meta(posts))
      end

      def create
        post = Post.new(post_params)
        if post.save
          render json: PostSerializer.new(post), status: :created
        else
          render json: { errors: post.errors }, status: :unprocessable_entity
        end
      end

      private

      def set_post
        @post = Post.find(params[:id])
      end

      def post_params
        params.require(:post).permit(:title, :body, :published)
      end
    end
  end
end
```

## Status codes

Key signals: `201` on create, `204` on delete, `422` on validation failure, `401` vs `403` for auth vs permission. See [references/status-codes.md](references/status-codes.md) for the full table.

## Error envelope

Pick one shape and keep it consistent across the API:

```json
{ "errors": { "title": ["can't be blank"] } }
```

JSON:API envelope is an acceptable alternative; pick one and stay consistent.

Centralize handling in `ApplicationController`:

```ruby
class ApplicationController < ActionController::API
  rescue_from ActiveRecord::RecordNotFound, with: :not_found
  rescue_from ActiveRecord::RecordInvalid,  with: :unprocessable

  private

  def not_found(e)
    render json: { error: e.message }, status: :not_found
  end

  def unprocessable(e)
    render json: { errors: e.record.errors }, status: :unprocessable_entity
  end
end
```

## Serialization

Don't `render json: @model` in anything beyond a scaffold. Use a dedicated serializer (`jsonapi-serializer`, `blueprinter`, or `alba`) so the response shape is explicit and decoupled from the DB schema.

## Versioning

Namespace the URL (`/api/v1/...`) from day one. It costs nothing now and is the only approach that doesn't bite later.

## Pagination

Use `kaminari` or `pagy`. Return pagination metadata either in the response body or in `Link` headers. Expose page size as a client-controllable param with a server-enforced cap (e.g., 100).

## Strong params

`params.require(:post).permit(:title, :body)` — always. Never pass raw `params` to `update`/`create`. For nested attributes, permit them explicitly: `permit(:title, comments_attributes: [:body])`.

## Auth (brief)

For token-based auth, prefer an `Authorization: Bearer <token>` header over query params or cookies. For stateful session auth in an API, you're almost certainly in the wrong architecture.
