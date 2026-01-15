# Render CLI Skill

Expert guidance for using the Render CLI to manage deployments, services, databases, and infrastructure on Render.com.

## Structure

```
render-cli/
├── SKILL.md                       # Main skill file (entry point)
├── README.md                      # This file
├── examples/                      # Complete working examples
│   ├── github-actions.yml         # GitHub Actions workflow
│   ├── gitlab-ci.yml              # GitLab CI/CD pipeline
│   └── deploy-script.sh           # Bash deployment script
└── references/                    # Extended reference material
    └── troubleshooting.md         # Comprehensive troubleshooting guide
```

## Usage

Invoke this skill when working with:
- Render CLI commands
- Deploying to Render
- Managing Render services and databases
- Setting up CI/CD pipelines with Render
- Troubleshooting Render CLI issues

## What This Skill Covers

### Core Commands
- Authentication (`render login`, API keys)
- Deployments (`render deploys create`, `--wait`, `--commit`)
- Service management (`render services`)
- Database access (`render psql`)
- SSH access (`render ssh`)
- Log viewing (`render logs`)

### Best Practices
- Security (API keys vs CLI tokens)
- Automation patterns
- Deployment safety
- CI/CD integration

### CI/CD Integration
- Complete GitHub Actions workflow
- GitLab CI/CD pipeline
- Custom bash deployment script
- Multi-environment setup (staging/production)

### Troubleshooting
- Authentication issues
- Deployment failures
- Database connection problems
- CI/CD integration issues
- Performance optimization

## Quick Start Examples

### Local Development
```bash
# Install and authenticate
brew install render
render login
render workspace set

# Deploy a service
render services  # Select service
render deploys create srv-abc123 --wait
```

### CI/CD (GitHub Actions)
See `examples/github-actions.yml` for a complete workflow with:
- Staging and production environments
- Manual and automatic deployments
- Deployment notifications
- Secret management

### Troubleshooting
See `references/troubleshooting.md` for detailed solutions to:
- Expired tokens
- Stuck deployments
- Connection issues
- CI/CD failures

## Skill Quality

- **Word count**: ~800 words in main SKILL.md (optimized for quick reference)
- **Progressive disclosure**: Core content in SKILL.md, detailed examples and troubleshooting in supporting files
- **Practical focus**: Emphasizes real-world commands and workflows
- **Safety-first**: Highlights security best practices and deployment safety

## Contributing

To improve this skill:
1. Add new examples to `examples/` directory
2. Expand troubleshooting scenarios in `references/troubleshooting.md`
3. Update SKILL.md with references to new supporting files
4. Test all commands and examples for accuracy

## Resources

- [Official Render CLI Documentation](https://render.com/docs/cli)
- [Render CLI GitHub Repository](https://github.com/render-oss/render-cli)
- [Render API Documentation](https://render.com/docs/api)
- [Render Community Forum](https://community.render.com)
