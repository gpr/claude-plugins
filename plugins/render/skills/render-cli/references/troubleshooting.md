# Render CLI Troubleshooting Guide

## Authentication Issues

### CLI Token Expired

**Symptoms**:
- Commands fail with "Unauthorized" or "Authentication failed"
- Error message: "Your CLI token has expired"

**Solution**:
```bash
# Re-authenticate via browser
render login

# Verify authentication
render services
```

**Prevention**:
- CLI tokens expire periodically (usually after 90 days)
- For long-term automation, use `RENDER_API_KEY` instead
- Set calendar reminders to re-authenticate before expiration

### API Key Not Working

**Symptoms**:
- `RENDER_API_KEY` environment variable set but commands fail
- Error: "Invalid API key"

**Diagnostics**:
```bash
# Check if API key is set
echo $RENDER_API_KEY

# Verify API key format (should start with "rnd_")
# Example: rnd_abc123def456...

# Test with explicit key
RENDER_API_KEY="rnd_your_key_here" render services
```

**Common causes**:
- API key copied incorrectly (extra spaces, line breaks)
- API key revoked in Render dashboard
- Using CLI token instead of API key (CLI tokens don't work for `RENDER_API_KEY`)
- Environment variable not exported: use `export RENDER_API_KEY="..."`

**Solution**:
```bash
# Regenerate API key
# 1. Visit https://dashboard.render.com/u/settings#api-keys
# 2. Delete old key
# 3. Create new key
# 4. Update environment variable

export RENDER_API_KEY="rnd_new_key_here"
render services  # Test
```

### Wrong Configuration File Path

**Symptoms**:
- `render login` succeeds but subsequent commands require re-authentication
- CLI doesn't remember login state

**Diagnostics**:
```bash
# Check default config location
ls -la ~/.render/cli.yaml

# Check if custom path is set
echo $RENDER_CLI_CONFIG_PATH

# Verify config file contents
cat ~/.render/cli.yaml
```

**Solution**:
```bash
# If using custom path, ensure it's always set
export RENDER_CLI_CONFIG_PATH=/custom/path/config.yaml

# Add to shell profile for persistence
echo 'export RENDER_CLI_CONFIG_PATH=/custom/path/config.yaml' >> ~/.bashrc
source ~/.bashrc

# If config is corrupted, re-authenticate
rm ~/.render/cli.yaml
render login
```

## Deployment Issues

### Deployment Stuck or Timing Out

**Symptoms**:
- `render deploys create --wait` hangs indefinitely
- Deployment shows "in progress" for abnormally long time

**Diagnostics**:
```bash
# Check deployment status
render deploys list [SERVICE_ID]

# View real-time logs
render logs [SERVICE_ID]

# Check service dashboard
# Visit https://dashboard.render.com/web/[SERVICE_ID]
```

**Common causes**:
- Build step hanging (missing dependency, infinite loop)
- Health check failing (service starts but fails health checks)
- Resource limits exceeded (out of memory, CPU throttling)

**Solution**:
```bash
# Cancel stuck deployment via dashboard
# 1. Visit service dashboard
# 2. Navigate to "Deploys" tab
# 3. Click "Cancel" on stuck deployment

# For future deployments, add timeout
timeout 600 render deploys create [SERVICE_ID] --wait  # 10 minute timeout

# Debug via SSH
render ssh [SERVICE_ID]
top          # Check resource usage
ps aux       # Check running processes
journalctl   # Check system logs
```

### Wrong Commit Deployed

**Symptoms**:
- Expected commit not deployed
- Old code running after deployment

**Diagnostics**:
```bash
# Check deployment history
render deploys list [SERVICE_ID]

# Verify commit SHA
git log -1 --oneline [COMMIT_SHA]

# Check if service is Git-backed or image-backed
render services  # Look for "Source" field
```

**Common causes**:
- Using `--commit` flag with image-backed service (not supported)
- Commit not pushed to remote repository
- Branch protection preventing deployment
- Cache not cleared (old build artifacts)

**Solution**:
```bash
# For Git-backed services, ensure commit is pushed
git push origin main

# Deploy specific commit
render deploys create [SERVICE_ID] --commit [CORRECT_SHA] --wait

# For image-backed services, use --image instead
render deploys create [SERVICE_ID] --image [IMAGE_URL:TAG] --wait

# Clear build cache via dashboard
# 1. Visit service settings
# 2. Navigate to "Build & Deploy"
# 3. Enable "Clear build cache"
```

### Service ID Not Found

**Symptoms**:
- Error: "Service not found"
- Error: "Invalid service ID"

**Diagnostics**:
```bash
# List all services in current workspace
render services

# Check workspace
render workspace list

# Verify service ID format (should be srv-xxxxx)
```

**Common causes**:
- Wrong workspace selected
- Service ID typo
- Service deleted or moved to different workspace

**Solution**:
```bash
# Switch to correct workspace
render workspace set

# List services to find correct ID
render services

# Copy exact service ID (e.g., srv-abc123def456)
render deploys create srv-abc123def456
```

## Database Connection Issues

### Cannot Connect to Database

**Symptoms**:
- `render psql [DATABASE_ID]` fails
- Error: "Connection refused" or "Timeout"

**Diagnostics**:
```bash
# Check database status
render services  # Look for database in list

# Verify database ID format (should be dpg-xxxxx)

# Check if database is running
# Visit https://dashboard.render.com
```

**Common causes**:
- Database suspended (free tier, payment issue)
- Database not fully provisioned yet
- Wrong database ID
- Network connectivity issue

**Solution**:
```bash
# Wait for database to be fully provisioned (can take 5-10 minutes)

# Verify database ID
render services  # Copy exact database ID

# Try again with correct ID
render psql dpg-abc123def456

# Check database logs in dashboard if issue persists
```

### psql Command Not Found

**Symptoms**:
- `render psql` fails with "psql: command not found"

**Cause**:
- PostgreSQL client tools not installed locally

**Solution**:
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql-client

# Verify installation
psql --version

# Retry
render psql [DATABASE_ID]
```

## SSH Access Issues

### SSH Connection Refused

**Symptoms**:
- `render ssh [SERVICE_ID]` fails
- Error: "Connection refused" or "Service not available"

**Common causes**:
- Service not running
- Service doesn't support SSH (static sites)
- Service type incompatible with SSH

**Diagnostics**:
```bash
# Check service status
render services

# Verify service type
# SSH only works with:
# - Web Services
# - Private Services
# - Background Workers

# Not supported for:
# - Static Sites
# - Cron Jobs
```

**Solution**:
```bash
# Ensure service is running
render deploys list [SERVICE_ID]  # Check if deployment succeeded

# Wait for service to be fully started (check logs)
render logs [SERVICE_ID]

# Retry SSH connection
render ssh [SERVICE_ID]
```

## CI/CD Integration Issues

### GitHub Actions: Permission Denied

**Symptoms**:
- Workflow fails with "Permission denied"
- Error: "Invalid API key" in GitHub Actions

**Diagnostics**:
```yaml
# Check secrets are set correctly
# Repository Settings > Secrets and variables > Actions

# Verify secret names match workflow:
- RENDER_API_KEY
- RENDER_SERVICE_ID
```

**Solution**:
```yaml
# Ensure secrets are correctly referenced
env:
  RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}

# Not:
env:
  RENDER_API_KEY: secrets.RENDER_API_KEY  # Wrong!

# Verify API key in Render dashboard
# https://dashboard.render.com/u/settings#api-keys

# Regenerate if necessary and update GitHub secret
```

### CLI Installation Fails in CI

**Symptoms**:
- `curl -fsSL https://install.render.com/latest | bash` fails
- CLI not found after installation

**Diagnostics**:
```bash
# Check CI environment
echo $PATH

# Verify installation directory
ls -la $HOME/.local/bin/
```

**Solution**:
```yaml
# Add CLI to PATH in CI workflow
- name: Install Render CLI
  run: |
    curl -fsSL https://install.render.com/latest | bash
    echo "$HOME/.local/bin" >> $GITHUB_PATH

# Verify installation
- name: Verify CLI
  run: render --version

# Alternative: Use full path
- name: Deploy
  run: $HOME/.local/bin/render deploys create ${{ secrets.RENDER_SERVICE_ID }}
```

## Performance Issues

### Slow Deployments

**Symptoms**:
- Deployments taking longer than expected
- Build step consuming most time

**Diagnostics**:
```bash
# Check deployment logs for bottlenecks
render logs [SERVICE_ID]

# Review build configuration
# Check Dockerfile or buildpack configuration
```

**Solutions**:
- Optimize Dockerfile (multi-stage builds, layer caching)
- Use `.dockerignore` to exclude unnecessary files
- Enable build cache in Render dashboard
- Consider upgrading to higher instance type

### CLI Commands Slow

**Symptoms**:
- `render` commands take long time to respond
- Noticeable lag in interactive operations

**Diagnostics**:
```bash
# Check network connectivity
ping render.com

# Test with verbose output
render services --debug
```

**Solutions**:
- Check internet connection stability
- Try different network (VPN, mobile hotspot)
- Update CLI to latest version: `brew upgrade render` or re-run installer
- Contact Render support if issue persists

## General Troubleshooting Steps

1. **Verify CLI version**:
   ```bash
   render --version
   # Update if outdated
   brew upgrade render  # macOS
   curl -fsSL https://install.render.com/latest | bash  # Linux
   ```

2. **Check authentication**:
   ```bash
   # Test with simple command
   render services

   # Re-authenticate if needed
   render login
   ```

3. **Verify workspace**:
   ```bash
   render workspace list
   render workspace set  # Switch if needed
   ```

4. **Enable debug output**:
   ```bash
   render --debug [COMMAND]
   # Provides verbose logging
   ```

5. **Check Render status**:
   - Visit https://status.render.com
   - Check for platform-wide issues

6. **Contact support**:
   - Visit https://render.com/support
   - Include CLI version, OS, and error messages
   - Provide output from `render --debug` if applicable

## Getting Additional Help

- **Documentation**: https://render.com/docs/cli
- **Community Forum**: https://community.render.com
- **GitHub Issues**: https://github.com/render-oss/render-cli/issues
- **Support**: https://render.com/support (paid plans get priority)
