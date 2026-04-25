---
name: tanstack-form-zod
description: Use when building forms. Schema-first with Zod; field-level + form-level validation; one shadcn input per field.
---

# TanStack Form + Zod

## Pattern
Schema first, form second. The Zod schema is the source of truth — also reused for API request validation.

```ts
const schema = z.object({
  email: z.string().email(),
  age: z.number().int().min(18),
})

const form = useForm({
  defaultValues: { email: '', age: 0 } satisfies z.input<typeof schema>,
  validators: { onChange: schema },
  onSubmit: async ({ value }) => { await mutate(value) },
})
```

## Fields
One `<form.Field>` per field. Bind to shadcn `<Input>` / `<Select>`. Pass `field.state.meta.errors` to the field's error slot.

```tsx
<form.Field
  name="email"
  children={(field) => (
    <FormItem>
      <Label htmlFor={field.name}>Email</Label>
      <Input
        id={field.name}
        value={field.state.value}
        onBlur={field.handleBlur}
        onChange={(e) => field.handleChange(e.target.value)}
      />
      {field.state.meta.errors.length > 0 && (
        <FormMessage>{field.state.meta.errors.join(', ')}</FormMessage>
      )}
    </FormItem>
  )}
/>
```

## Submit
Wrap submit in `e.preventDefault(); e.stopPropagation(); form.handleSubmit()`. Disable the submit button via `form.Subscribe` reading `state.canSubmit && !state.isSubmitting`.

## Async validation
Use `validators.onChangeAsyncDebounceMs: 300` with an async validator that calls the API. Return a string for error or `undefined` for success.

## Don'ts
- Don't use shadcn's `<Form>` from `react-hook-form` — that wrapper is RHF-specific. Use `<FormItem>`, `<Label>`, `<FormMessage>` primitives directly
- Don't duplicate the schema for client and server — export one from a shared module and import on both sides
