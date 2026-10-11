#!/usr/bin/env bash
# Shared helpers for release scripts. Source, don't execute.

# Print "<name> <path>" for every entry of [monorepo.packages] in cog.toml.
cog_packages() {
  sed -n '/^\[monorepo\.packages\]/,/^\[/p' "${1:-cog.toml}" |
    sed -nE 's/^([A-Za-z0-9_-]+)[[:space:]]*=[[:space:]]*\{[[:space:]]*path[[:space:]]*=[[:space:]]*"([^"]+)".*/\1 \2/p'
}
