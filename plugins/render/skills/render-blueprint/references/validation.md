# Render Blueprint Validation Guide

## Schema Validation

### JSON Schema URL
```
https://render.com/schema/render.yaml.json
```

### IDE Integration

#### VS Code
1. Install "YAML" extension by Red Hat
2. Add to `.vscode/settings.json`:
```json
{
  "yaml.schemas": {
    "https://render.com/schema/render.yaml.json": "render.yaml"
  }
}
```

#### JetBrains IDEs (IntelliJ, WebStorm, PyCharm)
1. Go to Settings → Languages & Frameworks → Schemas and DTDs → JSON Schema Mappings
2. Add new mapping:
   - Schema URL: `https://render.com/schema/render.yaml.json`
   - File path pattern: `render.yaml`

#### Neovim with yaml-language-server
Add to your LSP configuration:
```lua
require('lspconfig').yamlls.setup {
  settings = {
    yaml = {
      schemas = {
        ["https://render.com/schema/render.yaml.json"] = "render.yaml"
      }
    }
  }
}
```

### Command-Line Validation

Using `yq` and JSON schema validators:

```bash
# Install dependencies
npm install -g ajv-cli

# Download schema
curl -o render-schema.json https://render.com/schema/render.yaml.json

# Validate
ajv validate -s render-schema.json -d render.yaml
```

## Common Validation Errors

### 1. Missing Required Fields

#### Error: Missing 'type' field
```yaml
# ❌ Invalid
services:
  - name: api
    runtime: node
    buildCommand: npm install
    startCommand: npm start
```

**Solution**: Add required `type` field
```yaml
# ✅ Valid
services:
  - name: api
    type: web  # Required field
    runtime: node
    buildCommand: npm install
    startCommand: npm start
```

#### Error: Missing 'runtime' field
```yaml
# ❌ Invalid
services:
  - name: api
    type: web
    buildCommand: npm install
    startCommand: npm start
```

**Solution**: Add required `runtime` field
```yaml
# ✅ Valid
services:
  - name: api
    type: web
    runtime: node  # Required field
    buildCommand: npm install
    startCommand: npm start
```

#### Error: Missing 'schedule' for cron jobs
```yaml
# ❌ Invalid
services:
  - name: daily-job
    type: cron
    runtime: node
    buildCommand: npm install
    startCommand: node job.js
```

**Solution**: Add required `schedule` field
```yaml
# ✅ Valid
services:
  - name: daily-job
    type: cron
    runtime: node
    schedule: "0 0 * * *"  # Required for cron
    buildCommand: npm install
    startCommand: node job.js
```

### 2. Invalid Field Constraints

#### Error: Invalid disk size
```yaml
# ❌ Invalid - must be ≥1 and multiples of 5
disk:
  name: storage
  mountPath: /data
  sizeGB: 7
```

**Solution**: Use valid disk size
```yaml
# ✅ Valid
disk:
  name: storage
  mountPath: /data
  sizeGB: 10  # 1, 5, 10, 15, 20, etc.
```

#### Error: Invalid scaling percentages
```yaml
# ❌ Invalid - must be 1-90%
scaling:
  minInstances: 1
  maxInstances: 10
  targetCPUPercent: 95
```

**Solution**: Use valid range
```yaml
# ✅ Valid
scaling:
  minInstances: 1
  maxInstances: 10
  targetCPUPercent: 80  # 1-90
```

#### Error: Invalid shutdown delay
```yaml
# ❌ Invalid - must be 1-300 seconds
maxShutdownDelaySeconds: 600
```

**Solution**: Use valid range
```yaml
# ✅ Valid
maxShutdownDelaySeconds: 60  # 1-300 seconds
```

#### Error: Invalid region
```yaml
# ❌ Invalid
services:
  - name: api
    type: web
    runtime: node
    region: london
```

**Solution**: Use valid region
```yaml
# ✅ Valid
services:
  - name: api
    type: web
    runtime: node
    region: frankfurt  # oregon, ohio, virginia, frankfurt, singapore
```

### 3. Type Mismatches

#### Error: runtime specified for keyvalue
```yaml
# ❌ Invalid - keyvalue doesn't have runtime
services:
  - name: cache
    type: keyvalue
    runtime: redis
    plan: starter
```

**Solution**: Remove runtime field
```yaml
# ✅ Valid
services:
  - name: cache
    type: keyvalue
    plan: starter
```

#### Error: Wrong property type
```yaml
# ❌ Invalid - numInstances must be integer
services:
  - name: api
    type: web
    runtime: node
    numInstances: "2"
```

**Solution**: Use correct type
```yaml
# ✅ Valid
services:
  - name: api
    type: web
    runtime: node
    numInstances: 2
```

### 4. Invalid References

#### Error: Missing required fields in fromService
```yaml
# ❌ Invalid - missing 'type' field
envVars:
  - key: WORKER_HOST
    fromService:
      name: worker
      property: host
```

**Solution**: Add required type field
```yaml
# ✅ Valid
envVars:
  - key: WORKER_HOST
    fromService:
      name: worker
      type: pserv  # Required field
      property: host
```

#### Error: Invalid property name
```yaml
# ❌ Invalid - 'url' is not valid property
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: postgres
      property: url
```

**Solution**: Use valid property
```yaml
# ✅ Valid
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: postgres
      property: connectionString  # connectionString, host, port, user, password, database
```

#### Error: Referencing non-existent resource
```yaml
# ❌ Invalid - 'worker' service not defined
services:
  - name: api
    type: web
    runtime: node
    envVars:
      - key: WORKER_HOST
        fromService:
          name: worker  # This service doesn't exist!
          type: pserv
          property: host
```

**Solution**: Ensure referenced resource exists
```yaml
# ✅ Valid
services:
  - name: api
    type: web
    runtime: node
    envVars:
      - key: WORKER_HOST
        fromService:
          name: background-worker
          type: pserv
          property: host

  - name: background-worker  # Service exists
    type: pserv
    runtime: node
    buildCommand: npm install
    startCommand: npm start
```

### 5. Circular Dependencies

#### Error: Circular service references
```yaml
# ❌ Invalid - A references B, B references A
services:
  - name: service-a
    type: web
    runtime: node
    envVars:
      - key: SERVICE_B_HOST
        fromService:
          name: service-b
          type: web
          property: host

  - name: service-b
    type: web
    runtime: node
    envVars:
      - key: SERVICE_A_HOST
        fromService:
          name: service-a
          type: web
          property: host
```

**Solution**: Restructure to avoid cycles
```yaml
# ✅ Valid - Use shared database or message queue for coordination
services:
  - name: service-a
    type: web
    runtime: node
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString

  - name: service-b
    type: web
    runtime: node
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString

databases:
  - name: postgres
    databaseName: appdb
```

### 6. Static Site Configuration Errors

#### Error: buildCommand without publishPath
```yaml
# ❌ Invalid - publishPath required with buildCommand
services:
  - name: site
    type: static
    staticSiteDetails:
      buildCommand: npm run build
```

**Solution**: Add publishPath
```yaml
# ✅ Valid
services:
  - name: site
    type: static
    staticSiteDetails:
      buildCommand: npm run build
      publishPath: dist  # Required when buildCommand present
```

#### Error: Invalid route type
```yaml
# ❌ Invalid - 'proxy' is not valid type
services:
  - name: site
    type: static
    staticSiteDetails:
      publishPath: dist
      routes:
        - type: proxy
          source: /api/*
          destination: https://api.example.com
```

**Solution**: Use valid route types
```yaml
# ✅ Valid
services:
  - name: site
    type: static
    staticSiteDetails:
      publishPath: dist
      routes:
        - type: redirect  # redirect or rewrite
          source: /old-page
          destination: /new-page
          statusCode: 301
```

### 7. Docker Configuration Errors

#### Error: Both dockerfilePath and image specified
```yaml
# ❌ Invalid - can't use both
services:
  - name: api
    type: web
    runtime: docker
    dockerfilePath: ./Dockerfile
    image:
      fromRegistry: ghcr.io/user/repo:latest
```

**Solution**: Choose one approach
```yaml
# ✅ Valid - Dockerfile build
services:
  - name: api
    type: web
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .

# OR

# ✅ Valid - Pre-built image
services:
  - name: api
    type: web
    runtime: image
    image:
      fromRegistry: ghcr.io/user/repo:latest
```

#### Error: Missing dockerContext
```yaml
# ❌ Invalid - dockerContext required with dockerfilePath
services:
  - name: api
    type: web
    runtime: docker
    dockerfilePath: ./services/api/Dockerfile
```

**Solution**: Add dockerContext
```yaml
# ✅ Valid
services:
  - name: api
    type: web
    runtime: docker
    dockerfilePath: ./services/api/Dockerfile
    dockerContext: ./services/api
```

### 8. Environment Variable Errors

#### Error: Conflicting value sources
```yaml
# ❌ Invalid - can't use both 'value' and 'generateValue'
envVars:
  - key: SECRET
    value: hardcoded-secret
    generateValue: true
```

**Solution**: Use one value source
```yaml
# ✅ Valid
envVars:
  - key: SECRET
    generateValue: true
    sync: false
```

#### Error: generateValue with sync=true (implicit)
```yaml
# ⚠️ Warning - will regenerate secret on each deploy
envVars:
  - key: JWT_SECRET
    generateValue: true
```

**Best Practice**: Always set sync=false for secrets
```yaml
# ✅ Best Practice
envVars:
  - key: JWT_SECRET
    generateValue: true
    sync: false  # Preserve existing value
```

### 9. Preview Environment Errors

#### Error: Invalid generation value
```yaml
# ❌ Invalid - must be 'automatic' or 'manual'
previews:
  generation: auto
```

**Solution**: Use valid value
```yaml
# ✅ Valid
previews:
  generation: automatic  # or manual
  branch: main
```

#### Error: TTL too short
```yaml
# ❌ Invalid - minimum is 1 day
previews:
  generation: automatic
  branch: main
  ttl: 0
```

**Solution**: Use minimum 1 day
```yaml
# ✅ Valid
previews:
  generation: automatic
  branch: main
  ttl: 7  # Days
```

## Validation Best Practices

### 1. Pre-commit Validation
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash

# Validate render.yaml before commit
if [ -f render.yaml ]; then
    echo "Validating render.yaml..."
    ajv validate -s render-schema.json -d render.yaml
    if [ $? -ne 0 ]; then
        echo "❌ render.yaml validation failed"
        exit 1
    fi
    echo "✅ render.yaml is valid"
fi
```

### 2. CI/CD Validation
Add to GitHub Actions:
```yaml
- name: Validate Render Blueprint
  run: |
    npm install -g ajv-cli
    curl -o render-schema.json https://render.com/schema/render.yaml.json
    ajv validate -s render-schema.json -d render.yaml
```

### 3. Local Development
Add npm script to `package.json`:
```json
{
  "scripts": {
    "validate:render": "ajv validate -s render-schema.json -d render.yaml"
  }
}
```

### 4. Required Field Checklist

Before deploying, verify:

- [ ] All services have `name`, `type`, and `runtime` (except keyvalue)
- [ ] Web/worker services have `buildCommand` and `startCommand`
- [ ] Cron jobs have `schedule` field
- [ ] Static sites have `publishPath` (if using buildCommand)
- [ ] Docker services have `dockerfilePath` or `image`
- [ ] All `fromService` references include `type` field
- [ ] All `fromDatabase` references use valid properties
- [ ] Disk sizes are ≥1GB and multiples of 5
- [ ] Regions are valid (oregon, ohio, virginia, frankfurt, singapore)
- [ ] No circular dependencies between services
- [ ] Secrets use `generateValue: true` with `sync: false`
- [ ] Preview environment TTL ≥1 day

## Troubleshooting Deployment Failures

### Error: "Service failed to start"
**Check**:
1. Health check path returns 200 OK
2. Application listens on PORT environment variable
3. Build command completed successfully
4. Start command is correct

### Error: "Database connection failed"
**Check**:
1. Database `ipAllowList` includes `0.0.0.0/0` or service IP
2. Connection string property is correct
3. Database is fully provisioned (can take 5-10 minutes)

### Error: "Environment variable not found"
**Check**:
1. Variable defined in `envVars` or `envVarGroups`
2. Service references correct envVarGroup name
3. No typos in environment variable keys

### Error: "Build filter prevented deployment"
**Check**:
1. Changed files match `buildFilter.paths`
2. Files not in `buildFilter.ignoredPaths`
3. Verify with: `git diff --name-only HEAD~1 HEAD`

## Additional Resources

- Schema documentation: https://render.com/docs/blueprint-spec
- JSON schema: https://render.com/schema/render.yaml.json
- IDE setup guides: https://render.com/docs/yaml-ide-support
- Validation tools: https://github.com/ajv-validator/ajv-cli
