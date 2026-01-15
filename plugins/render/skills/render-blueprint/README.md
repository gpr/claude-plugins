# Render Blueprint Skill

Expert guidance for creating, validating, and troubleshooting Render Blueprint (render.yaml) infrastructure-as-code configurations.

## Structure

```
render-blueprint/
├── SKILL.md                           # Main skill file (entry point)
├── README.md                          # This file
├── examples/                          # Complete working examples
│   ├── fullstack-app.yaml            # Full-stack app with all service types
│   ├── monorepo.yaml                 # Monorepo configuration with buildFilter
│   ├── microservices.yaml            # Private services (pserv) architecture
│   ├── projects-environments.yaml    # Multi-environment setup (staging/prod)
│   └── docker-compose-migration.yaml # Migration from Docker Compose
└── references/                        # Extended reference material
    └── validation.md                 # Comprehensive validation guide
```

## Usage

Invoke this skill when working with:
- Creating or modifying `render.yaml` files
- Configuring Render services, databases, and caches
- Setting up monorepo deployments
- Validating Render Blueprint configurations
- Troubleshooting deployment issues
- Migrating from manual configuration or Docker Compose

## What This Skill Covers

### Service Configuration
- Web services (APIs, web applications)
- Worker services (background job processors)
- Cron jobs (scheduled tasks)
- Static sites (frontend builds)
- Private services (internal microservices)
- Redis/KeyValue stores (caching)

### Database Management
- PostgreSQL configuration
- Connection string management
- High availability setup
- Read replicas
- IP allow lists

### Advanced Features
- Environment variables and secrets
- Service interconnection (fromService, fromDatabase)
- Environment variable groups
- Auto-scaling configuration
- Persistent disk storage
- Custom domains
- Health checks
- Preview environments

### Monorepo Support
- Build filters (paths and ignoredPaths)
- Root directory configuration
- Shared package dependencies
- Selective rebuilds

### Docker Integration
- Dockerfile-based builds
- Pre-built image deployment
- Multi-stage builds
- Docker context configuration

## Quick Start Examples

### Basic Web Service
```yaml
services:
  - name: api
    type: web
    runtime: node
    buildCommand: npm install && npm build
    startCommand: npm start
```

### Full-Stack Application
See `examples/fullstack-app.yaml` for complete configuration with:
- React frontend (static site)
- Node.js API (web service)
- Background worker
- Cron jobs
- PostgreSQL database
- Redis cache

### Monorepo
See `examples/monorepo.yaml` for configuration with:
- Multiple apps and services
- Build filters for selective rebuilds
- Shared package dependencies
- Docker context for monorepo builds

### Docker Compose Migration
See `examples/docker-compose-migration.yaml` for migration guide from Docker Compose to Render Blueprint.

## Validation

### IDE Integration
- **VS Code**: Red Hat YAML extension with schema support
- **JetBrains**: JSON Schema Mappings configuration
- **Neovim**: yaml-language-server setup

### Command-Line Validation
```bash
# Install validator
npm install -g ajv-cli

# Download schema
curl -o render-schema.json https://render.com/schema/render.yaml.json

# Validate
ajv validate -s render-schema.json -d render.yaml
```

### Common Validation Errors
See `references/validation.md` for comprehensive guide covering:
- Missing required fields
- Invalid constraints
- Type mismatches
- Invalid references
- Circular dependencies
- Docker configuration errors
- Environment variable errors

## Best Practices

**Security**:
- Never hardcode secrets - use `generateValue: true`
- Set `sync: false` for generated secrets
- Configure `ipAllowList` for databases and Redis
- Use environment variable groups for shared config

**Performance**:
- Enable auto-scaling for variable workloads
- Configure health checks for zero-downtime deploys
- Use build filters in monorepos
- Set appropriate `maxShutdownDelaySeconds`

**Organization**:
- Use `envVarGroups` for shared configuration
- Define `rootDir` for monorepo services
- Use `projects` for environment separation
- Set reasonable preview environment TTL

**Deployment**:
- Set `autoDeploy: true` for continuous deployment
- Use `autoDeployTrigger: checksPass` to wait for CI
- Configure `preDeployCommand` for migrations
- Test with preview environments

## Skill Quality

- **Word count**: ~2,500 words in main SKILL.md
- **Progressive disclosure**: Core patterns in SKILL.md, detailed examples and validation in supporting files
- **Practical focus**: Real-world configurations and migration guides
- **Comprehensive validation**: Complete error reference with solutions

## Examples Included

1. **Full-Stack Application** (fullstack-app.yaml)
   - Frontend, API, worker, cron jobs
   - Database and cache configuration
   - Auto-scaling and health checks
   - Complete production-ready setup

2. **Monorepo Configuration** (monorepo.yaml)
   - Multiple apps with build filters
   - Shared package dependencies
   - Docker context for monorepo
   - Selective rebuild optimization

3. **Microservices Architecture** (microservices.yaml)
   - API Gateway pattern with private services (pserv)
   - Service-to-service communication
   - Inter-service references
   - Security best practices for internal services

4. **Multi-Environment Setup** (projects-environments.yaml)
   - Staging and production environments
   - Protected production deployments
   - Environment-specific configuration
   - Resource tier differences

5. **Docker Compose Migration** (docker-compose-migration.yaml)
   - Side-by-side comparison
   - Migration checklist
   - Key differences explained
   - Service interconnection patterns

## Contributing

To improve this skill:
1. Add new example configurations to `examples/`
2. Expand validation scenarios in `references/validation.md`
3. Update SKILL.md with new patterns and best practices
4. Test all examples for accuracy

## Resources

- [Render Blueprint Specification](https://render.com/docs/blueprint-spec)
- [JSON Schema](https://render.com/schema/render.yaml.json)
- [Render Services Documentation](https://render.com/docs/services)
- [Render Database Documentation](https://render.com/docs/databases)
- [IDE Support Guide](https://render.com/docs/yaml-ide-support)
