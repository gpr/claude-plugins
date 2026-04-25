---
name: zustand-slices
description: Use when adding client-only state (UI state, ephemeral selections, multi-step flows). Server state belongs in TanStack Query, not here.
---

# Zustand (slices pattern)

## Scope decision
- Server data → TanStack Query, **not** Zustand
- Auth → Clerk, **not** Zustand
- Form state → TanStack Form, **not** Zustand
- Zustand only for: UI state (sidebar open, theme), ephemeral cross-component selections, multi-step flow draft

## One store, sliced
Single `useAppStore`, composed of slices. Don't create N stores.

```ts
// src/store/index.ts
type UISlice = { sidebarOpen: boolean; toggleSidebar: () => void }
const createUISlice: StateCreator<UISlice & FlowSlice, [], [], UISlice> = (set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
})

export const useAppStore = create<UISlice & FlowSlice>()((...a) => ({
  ...createUISlice(...a),
  ...createFlowSlice(...a),
}))
```

## Selectors
Always select narrowly. Never `const state = useAppStore()` — that re-renders on every change.

```ts
const sidebarOpen = useAppStore((s) => s.sidebarOpen)
const toggle = useAppStore((s) => s.toggleSidebar)
```

For multiple values, use `useShallow`:
```ts
const { a, b } = useAppStore(useShallow((s) => ({ a: s.a, b: s.b })))
```

## Persistence
Only persist UI preferences (theme, sidebar). Never persist anything derivable from the API. Use the `persist` middleware with an explicit `partialize`.

## Actions
Define actions inside the slice, not in components. Components call actions; they don't `set` directly.
