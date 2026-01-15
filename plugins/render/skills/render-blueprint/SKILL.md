---
name: render-blueprint
description: |
  This skill should be used when the user asks about "render.yaml", "Render Blueprint", "infrastructure as code for Render", "validate render.yaml", "create render.yaml", mentions "Render IaC", needs help with "Render service configuration", "environment variables in render.yaml", "database configuration in Render", "monorepo with Render", or is troubleshooting "render.yaml validation errors", "blueprint deployment issues", "service interconnection in Render", wants to "generate render.yaml", "migrate to Render Blueprint", "configure preview environments", or needs examples of "web service configuration", "worker configuration", "cron job setup", "static site deployment", "Docker service on Render".
version: 1.0.0
---

# Render Blueprint Assistant

## Skill Instructions

When assisting with Render Blueprints (render.yaml), provide guidance on creating, validating, and troubleshooting infrastructure-as-code configurations for Render.

### What Are Render Blueprints?

Render Blueprints are infrastructure-as-code configurations defined in a `render.yaml` file at the repository root. They enable:
- Declarative, version-controlled infrastructure
- Reproducible deployments across services, databases, and caches
- Monorepo support with selective build triggers
- Automatic preview environments for pull requests

### Core Structure

```yaml
# Root-level sections
services:          # Web, worker, cron, static, private services
databases:         # PostgreSQL instances
envVarGroups:      # Reusable environment variable collections
projects:          # Organizational units with environments
previews:          # Preview environment generation rules
```

### Service Types

| Type | Purpose | Use Case |
|------|---------|----------|
| `web` | HTTP applications | APIs, web apps with public access |
| `pserv` | Private services | Internal microservices |
| `worker` | Background processors | Job queues, async tasks |
| `cron` | Scheduled tasks | Periodic jobs, cleanup scripts |
| `static` | Static content | Frontend builds, documentation sites |
| `keyvalue` | Redis cache | Session storage, caching layer |

### Required Fields

**All services**:
- `name`: Unique identifier
- `type`: Service category
- `runtime`: Environment (node, python, docker, image, go, ruby, rust, elixir, static)*

*Exception: `keyvalue` services don't specify runtime

**Non-Docker/image services**:
- `buildCommand`: Build steps
- `startCommand`: Start process (except static sites)

**Docker services**:
- `runtime: docker` requires `dockerfilePath` and `dockerContext`
- `runtime: image` requires `image.fromRegistry`

**Cron jobs**:
- `schedule`: Cron expression (e.g., `0 0 * * *`)

### Basic Service Configurations

#### Web Service (Node.js)
```yaml
services:
  - name: api
    type: web
    runtime: node
    buildCommand: npm install && npm run build
    startCommand: npm start
    autoDeploy: true  # Deploy automatically on git push
    envVars:
      - key: PORT
        value: 10000
      - key: NODE_ENV
        value: production
```

#### Worker Service (Python)
```yaml
services:
  - name: background-worker
    type: worker
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A tasks worker --loglevel=info
    envVars:
      - key: WORKER_CONCURRENCY
        value: 4
```

#### Cron Job
```yaml
services:
  - name: daily-cleanup
    type: cron
    runtime: python
    schedule: "0 0 * * *"  # Daily at midnight
    buildCommand: pip install -r requirements.txt
    startCommand: python cleanup.py
```

#### Static Site
```yaml
services:
  - name: frontend
    type: static
    staticSiteDetails:
      buildCommand: npm install && npm run build
      publishPath: dist
```

#### Docker Service (Build from Dockerfile)
```yaml
services:
  - name: custom-app
    type: web
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .
```

#### Pre-built Image Service
```yaml
services:
  - name: deployed-image
    type: web
    runtime: image
    image:
      fromRegistry: ghcr.io/username/repo:tag
      credentials:
        fromRegistryCreds: docker-registry-secret
```

### Environment Variables

#### Hardcoded Values
```yaml
envVars:
  - key: API_URL
    value: https://api.example.com
```

#### Generated Secrets
```yaml
envVars:
  - key: JWT_SECRET
    generateValue: true
    sync: false  # Preserve existing values
```

#### Service References
```yaml
envVars:
  - key: WORKER_HOST
    fromService:
      name: background-worker
      type: pserv
      property: host  # host, port, or hostport
```

#### Database References
```yaml
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: postgres-db
      property: connectionString
```

#### Environment Groups
```yaml
envVarGroups:
  - name: shared-config
    envVars:
      - key: LOG_LEVEL
        value: info
      - key: ENVIRONMENT
        value: production

services:
  - name: api
    type: web
    runtime: node
    envVarGroups:
      - shared-config
```

### Database Configuration

#### Basic PostgreSQL
```yaml
databases:
  - name: main-db
    databaseName: appdb
    region: oregon
    plan: standard-0
```

#### Advanced Database with High Availability
```yaml
databases:
  - name: production-db
    databaseName: proddb
    plan: standard-5
    region: oregon
    highAvailability:
      enabled: true
    ipAllowList:
      - 203.0.113.0/24  # Restrict access
    readReplicas:
      - name: replica-1
        region: ohio
```

### Monorepo Support

```yaml
services:
  - name: frontend
    type: web
    runtime: node
    rootDir: apps/frontend
    buildCommand: pnpm install && pnpm build
    buildFilter:
      paths:
        - "apps/frontend/**"
        - "packages/shared/**"
      ignoredPaths:
        - "apps/frontend/tests/**"

  - name: api
    type: web
    runtime: node
    rootDir: apps/api
    buildFilter:
      paths:
        - "apps/api/**"
        - "packages/shared/**"
```

### Preview Environments

```yaml
previews:
  generation: automatic  # or manual
  branch: main          # Generate for PRs to this branch
  ttl: 30              # Days before deletion

services:
  - name: api
    type: web
    runtime: node
    previews:
      enabled: true
      numInstances: 1  # Smaller for previews
```

### Advanced Configuration

#### Auto-scaling
```yaml
services:
  - name: api
    type: web
    runtime: node
    scaling:
      minInstances: 2
      maxInstances: 10
      targetCPUPercent: 80
      targetMemoryPercent: 75
```

#### Persistent Storage
```yaml
services:
  - name: media-processor
    type: worker
    runtime: python
    disk:
      name: uploads
      mountPath: /data
      sizeGB: 50
```

#### Health Checks
```yaml
services:
  - name: api
    type: web
    runtime: node
    healthCheckPath: /health
    maxShutdownDelaySeconds: 60
```

#### Custom Domains
```yaml
services:
  - name: web-app
    type: web
    runtime: node
    domains:
      - example.com
      - www.example.com
```

#### Static Site Routing
```yaml
services:
  - name: docs
    type: static
    staticSiteDetails:
      buildCommand: npm run build
      publishPath: dist
      routes:
        - type: redirect
          source: /old-page
          destination: /new-page
          statusCode: 301
        - type: rewrite
          source: /docs/*
          destination: /index.html
      headers:
        - path: /*
          headers:
            - name: Cache-Control
              value: public, max-age=31536000
```

### Complete Example: Full Stack App

```yaml
services:
  # Frontend
  - name: webapp
    type: static
    staticSiteDetails:
      buildCommand: npm install && npm run build
      publishPath: dist
    envVars:
      - key: API_URL
        fromService:
          name: api
          type: web
          property: hostport

  # Backend API
  - name: api
    type: web
    runtime: node
    buildCommand: npm install && npm run build
    startCommand: npm start
    healthCheckPath: /api/health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: cache
          type: keyvalue
          property: hostport
      - key: JWT_SECRET
        generateValue: true
        sync: false

  # Background Worker
  - name: worker
    type: worker
    runtime: node
    buildCommand: npm install && npm run build
    startCommand: npm run worker
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: cache
          type: keyvalue
          property: hostport

  # Scheduled Job
  - name: cleanup
    type: cron
    schedule: "0 2 * * *"  # 2 AM daily
    runtime: node
    buildCommand: npm install
    startCommand: node scripts/cleanup.js
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString

  # Redis Cache
  - name: cache
    type: keyvalue
    plan: free
    ipAllowList:
      - 0.0.0.0/0

# Database
databases:
  - name: postgres
    databaseName: appdb
    plan: standard-0

# Shared Environment Variables
envVarGroups:
  - name: common
    envVars:
      - key: NODE_ENV
        value: production
      - key: LOG_LEVEL
        value: info
```

### Validation

**JSON Schema**: Validate against `https://render.com/schema/render.yaml.json`

**IDE Support**:
- VS Code: Install Red Hat YAML extension
- Add to settings.json:
```json
{
  "yaml.schemas": {
    "https://render.com/schema/render.yaml.json": "render.yaml"
  }
}
```

**Common Validation Errors**:

1. **Missing required fields**
   ```yaml
   # Error: Missing 'type'
   services:
     - name: api
       runtime: node

   # Fix: Add 'type'
   services:
     - name: api
       type: web
       runtime: node
   ```

2. **Invalid constraints**
   ```yaml
   # Error: Disk size must be ≥1GB and multiples of 5
   disk:
     sizeGB: 7

   # Fix: Use valid size
   disk:
     sizeGB: 10
   ```

3. **Circular references**
   ```yaml
   # Error: Service A references B, B references A
   # Fix: Restructure to avoid cycles
   ```

4. **Type mismatches**
   ```yaml
   # Error: keyvalue shouldn't specify runtime
   services:
     - name: cache
       type: keyvalue
       runtime: redis  # Wrong!

   # Fix: Remove runtime
   services:
     - name: cache
       type: keyvalue
   ```

### Best Practices

**Security**:
- Never hardcode secrets in `render.yaml`
- Use `generateValue: true` for sensitive data
- Set `sync: false` to preserve existing secrets
- Configure `ipAllowList` for databases and Redis

**Performance**:
- Enable auto-scaling for variable workloads
- Set appropriate `healthCheckPath` for zero-downtime deploys
- Configure `maxShutdownDelaySeconds` for graceful shutdowns
- Use `buildFilter` in monorepos to avoid unnecessary builds

**Organization**:
- Use `envVarGroups` for shared configuration
- Define `rootDir` for monorepo services
- Use `projects` to separate staging/production
- Set reasonable `ttl` for preview environments

**Deployment**:
- Set `autoDeploy: true` for continuous deployment
- Use `autoDeployTrigger: checksPass` to wait for CI
- Configure `preDeployCommand` for migrations
- Test with preview environments before production

### Migration from Manual Configuration

1. **Export existing configuration**:
   ```bash
   render config export > render.yaml
   ```

2. **Add to repository**:
   ```bash
   git add render.yaml
   git commit -m "feat: add Render Blueprint"
   git push
   ```

3. **Connect in Render Dashboard**:
   - Link repository to service
   - Blueprint auto-applies on commit

4. **Verify synchronization**:
   - Check dashboard for applied changes
   - Monitor deployment logs

### Guidance Approach

**Clarify requirements first**:
- Identify service types needed (web, worker, cron, static, pserv)
- Determine runtime environments
- Understand database and cache requirements
- Check for monorepo structure
- Assess environment separation needs (staging, production)

**Provide complete configurations**:
- Include all required fields
- Add helpful comments
- Show environment variable patterns
- Demonstrate service interconnections
- Consider security best practices

**Validate before deployment**:
- Check against JSON schema
- Verify field constraints (disk sizes, regions, etc.)
- Test for circular references
- Confirm security best practices (no hardcoded secrets)

**Consider architecture**:
- Suggest appropriate service types (pserv for internal services)
- Recommend auto-scaling when beneficial
- Propose preview environments for testing
- Guide on monorepo buildFilter usage
- Consider projects for environment separation

### Common Patterns

For detailed examples and troubleshooting, see:
- `examples/fullstack-app.yaml` - Complete application with all service types
- `examples/monorepo.yaml` - Monorepo with buildFilter configuration
- `examples/microservices.yaml` - Private services (pserv) architecture
- `examples/projects-environments.yaml` - Multi-environment setup
- `examples/docker-compose-migration.yaml` - Migration from Docker Compose
- `references/validation.md` - Validation rules and error solutions

### Resources

- Specification: https://render.com/docs/blueprint-spec
- JSON Schema: https://render.com/schema/render.yaml.json
- Service configuration: https://render.com/docs/services
- Database setup: https://render.com/docs/databases
