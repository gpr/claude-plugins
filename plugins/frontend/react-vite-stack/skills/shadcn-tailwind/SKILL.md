---
name: shadcn-tailwind
description: "Applies shadcn/ui CLI and Tailwind v4 conventions for UI work. Invoke when adding UI primitives via the shadcn CLI, styling components with Tailwind utilities, or configuring the design-token theme."
---

# shadcn/ui + Tailwind

## Adding components
Use the CLI — never copy from the website manually.

```bash
pnpm dlx shadcn@latest add button input dialog
```

Components land in `src/components/ui/`. Treat them as **owned source**: edit freely. Don't reinstall over local edits unless intentional.

## Styling rules
- All styling via Tailwind utility classes; no `.css` files except `globals.css`
- Use `cn()` from `src/lib/utils.ts` to merge classes — never template-string concat
- Variants via `class-variance-authority`; the shadcn-generated components show the pattern — copy it

```tsx
import { cn } from '@/lib/utils'
<div className={cn('rounded-md p-4', isActive && 'bg-primary text-primary-foreground', className)} />
```

## Dark mode
Use `next-themes` (works in plain Vite too) with `ThemeProvider` at root. Never branch on `theme` in JSX — use Tailwind's `dark:` variant.

## Tokens
All colors via CSS variables defined in `globals.css` and consumed as `bg-background`, `text-foreground`, `border-border`, etc. Never use raw hex or `bg-blue-500` for app chrome.

## Composition
- Build feature components by composing `ui/` primitives, not by restyling them
- Feature components live in `src/components/<feature>/`; primitives stay in `src/components/ui/`

## Don'ts
- No Tailwind `@apply` outside `globals.css`
- No CSS-in-JS (no styled-components, no emotion)
- No inline `style={{}}` except for dynamic numeric values (computed positions, percentages)
