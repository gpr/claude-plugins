---
name: lsp-code-search
description: Knowledge base for LSP-first code search in Python projects. Use for GUIDANCE on finding definitions, references, callers, and type info using pyright LSP instead of Grep. NOT for running tests or linting (handled automatically by hooks). Triggers on "find definition", "find references", "who calls", "where is", "go to definition", "callers of", "implementations of", "symbol search", "type of", "hover info", "what calls", "usage of", "pyright", "LSP commands".
---

# LSP-First Code Search

Use pyright LSP for precise, type-aware code navigation in Python projects. LSP resolves imports, follows re-exports, and understands class hierarchies — Grep only matches text.

## Decision Matrix

| Task | Use | Why |
|------|-----|-----|
| Find where a function/class is defined | LSP `goToDefinition` | Resolves imports, follows re-exports |
| Find all usages of a symbol | LSP `findReferences` | Type-aware, no false positives from string matches |
| Find who calls a function | LSP `incomingCalls` | Follows call graph, not text patterns |
| Find what a function calls | LSP `outgoingCalls` | Shows actual call targets |
| Get type signature or docstring | LSP `hover` | Returns resolved type and docs |
| List all symbols in a file | LSP `documentSymbol` | Structured tree with nesting |
| Search for a symbol by name | LSP `workspaceSymbol` | Finds by symbol name across workspace |
| Find implementations of abstract method | LSP `goToImplementation` | Follows class hierarchy |
| Find a string literal, log message, or comment | **Grep** | LSP only knows symbols |
| Find files by name pattern | **Glob** | File system search |
| Search non-Python files (YAML, JSON, MD) | **Grep** | pyright covers `.py`/`.pyi` only |

## Operations Quick Reference

All operations require `filePath`, `line`, `character` (1-based). Position the cursor **on the symbol name**.

| Operation | When to use | Non-obvious behavior |
|-----------|-------------|----------------------|
| `goToDefinition` | Jump from usage to source | Follows re-exports across modules |
| `findReferences` | All usages before refactoring | Type-aware — no false positives from string matches |
| `hover` | Quick type/docstring inspection | Returns resolved type, not just declared type |
| `documentSymbol` | List all symbols in a file | Position irrelevant — use `line=1 character=1` |
| `workspaceSymbol` | Find symbol by name, unknown file | Position irrelevant — use `line=1 character=1` |
| `goToImplementation` | Find concrete classes for ABC/Protocol | Follows class hierarchy, not text |
| `prepareCallHierarchy` | Get call hierarchy item at position | Prerequisite for incoming/outgoing calls |
| `incomingCalls` | "Who calls this function?" | Traces call graph upstream |
| `outgoingCalls` | "What does this function call?" | Traces call graph downstream |

## Workflow Patterns

### Understand an unfamiliar function

1. `hover` on the function name — get type signature and docstring
2. `goToDefinition` — read the implementation
3. `incomingCalls` — see how it's used elsewhere

### Safe refactoring

1. `findReferences` — locate every usage before changing
2. `hover` on ambiguous usages — confirm type matches
3. Make changes, then `findReferences` again — verify nothing was missed

### Trace a call chain

1. `incomingCalls` on the target — find callers
2. `outgoingCalls` on each caller — understand the broader flow
3. `goToDefinition` on unfamiliar symbols — read their source

### Explore an unfamiliar module

1. `documentSymbol` — get the full symbol tree
2. `hover` on interesting symbols — quick type/doc info
3. `goToImplementation` on abstract methods — find concrete classes

### Find a symbol when you only know the name

1. `workspaceSymbol` — search by name across the workspace
2. `goToDefinition` — jump to the result
3. `findReferences` — see all usages

## Important Notes

- **All 4 parameters required:** Every LSP call needs `operation`, `filePath`, `line`, `character`.
- **1-based coordinates:** Line and character are 1-based (as shown in editors), not 0-based.
- **Position on the symbol:** The `character` must point to a character within the symbol name, not whitespace or punctuation.
- **pyright coverage:** Only `.py` and `.pyi` files. For YAML, JSON, Markdown, or other file types, fall back to Grep.
- **Empty results:** If LSP returns nothing, the symbol may be dynamically generated (`getattr`, metaclass, `__init_subclass__`). Fall back to Grep with the symbol name as a string search.
- **Grep is still useful:** Use Grep for string literals (`"error_code"`), log messages, comments, and cross-language searches. LSP and Grep are complementary, not competing.
