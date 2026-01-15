---
name: render-cli
description: |
  This skill should be used when the user asks about "Render CLI", "render command", "render login", "render deploys", "render psql", "render ssh", "render services", "deploy to Render", "Render deployment", "Render.com CLI", mentions "RENDER_API_KEY", needs help with "Render CI/CD integration", "GitHub Actions with Render", "PostgreSQL access on Render", "SSH into Render service", or is troubleshooting "Render authentication", "Render deployment failure", "Render database connection", "Render CLI token expired", or wants to "trigger Render deployment", "access Render database", "view Render logs", or "automate Render deployments".
version: 1.0.0
---

# Render CLI Assistant

## Skill Instructions

When assisting with the Render CLI, provide guidance on managing Render services and infrastructure through the command-line tool.

### Core Capabilities

The Render CLI enables:
- **Deployment Management**: Trigger and monitor deployments
- **Database Access**: Direct psql sessions to PostgreSQL databases
- **Service Management**: List, inspect, and manage services
- **Real-time Monitoring**: View and filter service logs
- **SSH Access**: Debug running service instances
- **CI/CD Automation**: Non-interactive mode with structured output

### Key Commands Reference

#### Authentication
```bash
# Interactive login (for local development)
render login

# Automated authentication (for CI/CD)
export RENDER_API_KEY="your-api-key"
```

**Important**:
- CLI tokens (from `render login`) expire periodically
- API keys never expire but should only be used in automated environments
- Configuration stored at `~/.render/cli.yaml` or `$RENDER_CLI_CONFIG_PATH`

#### Workspace Management
```bash
# Set active workspace (affects all subsequent commands)
render workspace set
```

#### Service Operations
```bash
# List all services and datastores (interactive menu)
render services

# View deployment history
render deploys list [SERVICE_ID]

# Trigger new deployment
render deploys create [SERVICE_ID]                    # Deploy from main branch
render deploys create [SERVICE_ID] --commit [SHA]     # Deploy specific commit
render deploys create [SERVICE_ID] --image [URL]      # Deploy specific image
render deploys create [SERVICE_ID] --wait             # Wait for completion
render deploys create [SERVICE_ID] --confirm          # Skip confirmation prompts
```

#### Database Access
```bash
# Open psql session to PostgreSQL database
render psql [DATABASE_ID]
```

#### Debugging
```bash
# Open SSH session to running service
render ssh [SERVICE_ID]

# View service logs
render logs [SERVICE_ID]
```

#### Help
```bash
# Get help for any command
render help [COMMAND]
```

### Common Workflows

#### Local Development Setup
1. Install CLI: `brew install render` (macOS) or use curl installer
2. Authenticate: `render login`
3. Set workspace: `render workspace set`
4. Access database: `render psql [DATABASE_ID]`

#### Manual Deployment
```bash
# Interactive deployment
render services        # Select service
render deploys create  # Trigger deployment

# Or with service ID
render deploys create srv-xyz123 --wait
```

#### CI/CD Integration

For complete CI/CD integration examples, see:
- `examples/github-actions.yml` - GitHub Actions workflow with staging/production
- `examples/gitlab-ci.yml` - GitLab CI/CD pipeline
- `examples/deploy-script.sh` - Bash deployment script for custom CI/CD

Basic GitHub Actions deployment:
```yaml
- name: Install Render CLI
  run: curl -fsSL https://install.render.com/latest | bash

- name: Deploy to Render
  env:
    RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
  run: |
    render deploys create ${{ secrets.RENDER_SERVICE_ID }} \
      --commit ${{ github.sha }} \
      --wait \
      --confirm
```

### Best Practices

#### Security
- ✅ Use `render login` for local development
- ✅ Use `RENDER_API_KEY` only in CI/CD or secure automation
- ✅ Store API keys in environment variables or secrets management
- ✅ Revoke compromised tokens via Account Settings dashboard
- ❌ Never commit API keys to version control
- ❌ Don't use API keys for local manual operations

#### Automation
- Pin CLI version in CI/CD: ensures consistency
- Use `--confirm` flag: skips interactive prompts
- Use `--wait` flag: blocks until deployment completes
- Use `--output json|yaml`: structured output for parsing
- Set `RENDER_API_KEY`: bypasses interactive authentication

#### Deployment Safety
- Always verify workspace before deploying: `render workspace set`
- Use `--commit [SHA]` for reproducible Git-backed deployments
- Use `--image [URL]` for reproducible image-backed deployments
- Test deployments in staging environment first
- Monitor deployment logs during and after deployment

### Common Gotchas

1. **CLI tokens expire periodically**: Re-run `render login` if authentication fails
2. **API keys never expire**: More suitable for automation but less secure for local use
3. **Workspace context matters**: Wrong workspace = deploying to wrong environment
4. **Service must be running**: SSH and psql require active service instances
5. **Git vs Image deployments**: Use correct flag (`--commit` vs `--image`) for service type

### Troubleshooting

For comprehensive troubleshooting guidance, see `references/troubleshooting.md`

Common quick fixes:

**Authentication Issues**:
```bash
render login  # Re-authenticate if token expired
cat ~/.render/cli.yaml  # Check configuration
```

**Deployment Issues**:
```bash
render deploys list [SERVICE_ID]  # Check deployment history
render logs [SERVICE_ID]  # View deployment logs
```

**Database Connection Issues**:
```bash
render services  # Ensure database is running
render psql [DATABASE_ID]  # Verify database ID
```

### Installation

```bash
# macOS via Homebrew
brew install render

# Linux/macOS via curl
curl -fsSL https://install.render.com/latest | bash

# Manual download
# Visit https://github.com/render-oss/render-cli/releases
```

### Guidance Approach

**Clarify context first**:
- Determine if working locally or in CI/CD
- Identify target workspace/environment
- Confirm service type (Git-backed vs image-backed)

**Recommend appropriate authentication**:
- Local development → `render login`
- CI/CD automation → `RENDER_API_KEY`

**Provide complete commands**:
- Include necessary flags (`--confirm`, `--wait`)
- Show output format options when relevant
- Explain each flag's purpose

**Consider safety**:
- Warn about production deployments
- Suggest staging environment testing first
- Recommend specific commits/images for reproducibility

**Troubleshoot systematically**:
- Verify authentication status
- Check workspace context
- Confirm service IDs
- Review deployment history and logs

### Additional Resources

- Official documentation: https://render.com/docs/cli
- GitHub repository: https://github.com/render-oss/render-cli
- API documentation: https://render.com/docs/api
- Support: https://render.com/support

## Examples

### Example 1: First-time Setup
```bash
# Install CLI
brew install render

# Authenticate
render login

# Set workspace
render workspace set

# List services
render services
```

### Example 2: Deploy Specific Commit
```bash
# Deploy commit abc123 to service srv-xyz and wait for completion
render deploys create srv-xyz --commit abc123 --wait
```

### Example 3: CI/CD Deployment
```bash
# In GitHub Actions or similar
export RENDER_API_KEY="${RENDER_API_KEY}"
render deploys create srv-xyz --commit ${GITHUB_SHA} --confirm --wait
```

### Example 4: Database Access
```bash
# Open psql to run migrations or queries
render psql dpg-abc123

# Then run SQL commands
\dt              # List tables
SELECT * FROM users LIMIT 10;
```

### Example 5: Debug Production Issue
```bash
# View recent logs
render logs srv-xyz

# SSH into instance for deeper investigation
render ssh srv-xyz

# Check running processes
ps aux

# Exit SSH
exit
```
