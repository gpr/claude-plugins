#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook: environment setup for Python projects
source "$(dirname "$0")/_lib.sh"

project_root=$(find_project_root "${CLAUDE_PROJECT_DIR:-.}") || exit 0
workspace_root=$(find_workspace_root "$project_root")

# Only install tooling in remote environments
if [[ "${CLAUDE_CODE_REMOTE:-}" == "true" ]]; then

  ENV_BEFORE=$(export -p | sort)

  # --- Install and activate mise if config exists ---
  mise_config_dir=""
  for dir in "$workspace_root" "$project_root"; do
    if [[ -f "$dir/mise.toml" || -f "$dir/.mise.toml" ]]; then
      mise_config_dir="$dir"
      break
    fi
  done

  if [[ -n "$mise_config_dir" ]]; then
    if ! command -v mise &>/dev/null; then
      # Prefer local bin/mise (from `mise bootstrap`) over internet install
      local_mise=""
      for dir in "$project_root" "$workspace_root"; do
        if [[ -x "$dir/bin/mise" ]]; then
          local_mise="$dir/bin/mise"
          break
        fi
      done

      if [[ -n "$local_mise" ]]; then
        export PATH="$(dirname "$local_mise"):$PATH"
      else
        curl https://mise.run | sh
        export PATH="$HOME/.local/bin:$PATH"
      fi

      if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
        echo "PATH=$PATH" >> "$CLAUDE_ENV_FILE"
      fi
    fi

    cd "$mise_config_dir" && mise trust && mise install --yes
    eval "$(cd "$mise_config_dir" && mise env --shell bash)"
  fi

  # --- Install uv if missing ---
  if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    # Persist PATH for subsequent Claude Bash tool calls
    if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
      echo "PATH=$HOME/.local/bin:$PATH" >> "$CLAUDE_ENV_FILE"
    fi
  fi

  if [ -n "$CLAUDE_ENV_FILE" ]; then
    ENV_AFTER=$(export -p | sort)
    comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
  fi

fi

# --- uv sync (use workspace root for monorepo) ---
if [[ -f "$workspace_root/pyproject.toml" ]]; then
  cd "$workspace_root" && uv sync
fi
